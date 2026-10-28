import asyncio
import logging
from contextlib import AsyncExitStack
from contextlib import asynccontextmanager
from datetime import UTC
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from normative_conformance.errors import CaptureDisconnected
from normative_conformance.errors import CaptureFailure
from normative_conformance.services.capture import run_capture as module
from normative_conformance.services.capture.transcriber import SpeakerRevised
from normative_conformance.services.capture.transcriber import SpeechStarted
from normative_conformance.services.capture.transcriber import TurnRevision
from normative_conformance.services.capture.transcriber import TurnUpdate
from normative_conformance.services.capture.transcriber import Word

END = object()


class FakeTranscriber:
    """Record forwarded audio; each test supplies the events the provider would send."""

    session_id = "session-123"
    speech_model = "test-model"

    def __init__(self, *, on_audio=(), on_finish=(), end_on_finish=True):
        self.audio = []
        self.finished = 0
        self._on_audio = on_audio
        self._on_finish = on_finish
        self._end_on_finish = end_on_finish
        self._events = asyncio.Queue()

    def emit(self, *events):
        for event in events:
            self._events.put_nowait(event)

    async def send_audio(self, pcm):
        self.audio.append(pcm)
        self.emit(*self._on_audio)

    async def finish(self):
        self.finished += 1
        self.emit(*self._on_finish)
        if self._end_on_finish:
            self.emit(END)

    async def events(self):
        while (event := await self._events.get()) is not END:
            if isinstance(event, Exception):
                raise event
            yield event


def connecting(transcriber):
    @asynccontextmanager
    async def connect():
        yield transcriber

    return connect


async def browser(*messages):
    for message in messages:
        yield message


async def run(*, case_id, messages, transcriber, now, store_observations, store_revisions):
    sent = []

    async def send(message):
        sent.append(message)

    await asyncio.wait_for(
        module.run_capture(
            case_id=case_id,
            now=now,
            store_observations=store_observations,
            store_revisions=store_revisions,
            messages=messages,
            send=send,
            connect_transcriber=connecting(transcriber),
        ),
        1,
    )
    return sent


def test_streams_levels_and_transcripts_until_stopped(caplog):
    caplog.set_level(logging.INFO, logger="normative_conformance.services.capture")
    transcriber = FakeTranscriber(
        on_audio=[
            TurnUpdate(
                turn_order=0, final=False, speaker_id="PENDING", transcript="Hello", words=()
            )
        ],
        on_finish=[
            SpeechStarted(),
            TurnUpdate(
                turn_order=0,
                final=True,
                speaker_id="A",
                transcript="Hello there.",
                words=(
                    Word(text="Hello", start_ms=0, end_ms=60, speaker_id="A"),
                    Word(text="there.", start_ms=60, end_ms=100, speaker_id=None),
                ),
            ),
            SpeakerRevised(
                turns=(
                    TurnRevision(
                        turn_order=0,
                        speaker_id="B",
                        words=(
                            Word(text="Hello", start_ms=0, end_ms=60, speaker_id="B"),
                            Word(text="there.", start_ms=60, end_ms=100, speaker_id="B"),
                        ),
                    ),
                )
            ),
        ],
    )
    audio = b"\x00\x00" * 1600 + b"\x00\x80" * 80

    sent = asyncio.run(
        run(
            case_id="capture-case",
            now=lambda: datetime(2026, 10, 26, tzinfo=UTC),
            store_observations=AsyncMock(),
            store_revisions=AsyncMock(),
            messages=browser(audio[:3200], audio[3200:], "stop"),
            transcriber=transcriber,
        )
    )

    assert sent[0] == {
        "type": "ready",
        "case_id": "capture-case",
        "sample_rate": 16000,
        "encoding": "pcm_s16le",
        "channels": 1,
        "session_id": "session-123",
        "speech_model": "test-model",
    }
    assert sent[-1] == {"type": "stopped"}
    assert b"".join(transcriber.audio) == audio
    assert transcriber.finished == 1
    levels = [f for m in sent if m["type"] == "levels" for f in m["frames"]]
    assert levels == [
        {"start_ms": start, "end_ms": start + 20, "dbfs": -120} for start in [0, 20, 40, 60, 80]
    ] + [{"start_ms": 100, "end_ms": 105, "dbfs": 0}]
    transcripts = [m for m in sent if m["type"] == "transcript"]
    assert [t["final"] for t in transcripts] == [False, True, True]
    assert transcripts[1]["words"][1]["speaker_id"] is None
    assert transcripts[-1] == {
        "type": "transcript",
        "turn_order": 0,
        "final": True,
        "revised": True,
        "transcript": "Hello there.",
        "speaker_id": "B",
        "words": [
            {"text": "Hello", "start_ms": 0, "end_ms": 60, "speaker_id": "B"},
            {"text": "there.", "start_ms": 60, "end_ms": 100, "speaker_id": "B"},
        ],
    }
    # Logs are the requested diagnostic output here; capture behavior is asserted above.
    records = [
        r for r in caplog.records if r.name.startswith("normative_conformance.services.capture")
    ]
    assert len({r.capture_id for r in records}) == 1
    assert {r.event for r in records} == {
        "capture.connected",
        "capture.provider_ready",
        "capture.audio_forwarded",
        "capture.stopping",
        "capture.speech_started",
        "capture.transcript_received",
        "capture.speaker_revisions",
        "capture.completed",
    }
    provider_ready = next(r for r in records if r.event == "capture.provider_ready")
    assert provider_ready.provider_session_id == "session-123"
    assert provider_ready.speech_model == "test-model"
    received = [r for r in records if r.event == "capture.transcript_received"]
    assert [(r.turn_order, r.final, r.character_count) for r in received] == [
        (0, False, 5),
        (0, True, 12),
    ]
    assert all("transcript" not in r.__dict__ for r in records)
    assert "Hello there." not in caplog.text


def test_browser_leaving_before_stop_is_a_disconnect_without_stopped():
    sent = []

    async def send(message):
        sent.append(message)

    with pytest.raises(CaptureDisconnected):
        asyncio.run(
            module.run_capture(
                case_id="capture-case",
                now=lambda: datetime(2026, 10, 26, tzinfo=UTC),
                store_observations=AsyncMock(),
                store_revisions=AsyncMock(),
                messages=browser(b"\x00\x00" * 1600),
                send=send,
                connect_transcriber=connecting(FakeTranscriber()),
            )
        )
    assert [m["type"] for m in sent] == ["ready", "levels"]


@pytest.mark.parametrize(
    "event,expected",
    [
        (END, "incomplete"),
        (CaptureFailure("providerProtocol"), "providerProtocol"),
        (CaptureFailure("providerUnavailable"), "providerUnavailable"),
    ],
)
def test_provider_failure_cancels_waiting_browser_input(event, expected):
    cancelled = asyncio.Event()

    async def waiting_browser():
        try:
            await asyncio.Future()
        finally:
            cancelled.set()
        yield b""

    async def scenario():
        transcriber = FakeTranscriber()
        transcriber.emit(event)
        with pytest.raises(CaptureFailure) as caught:
            await run(
                case_id="capture-case",
                now=lambda: datetime(2026, 10, 26, tzinfo=UTC),
                store_observations=AsyncMock(),
                store_revisions=AsyncMock(),
                messages=waiting_browser(),
                transcriber=transcriber,
            )
        assert caught.value.code == expected
        assert cancelled.is_set()

    asyncio.run(scenario())


def test_connection_failure_sends_nothing():
    @asynccontextmanager
    async def connect():
        raise CaptureFailure("notConfigured")
        yield

    sent = []

    async def send(message):
        sent.append(message)

    with pytest.raises(CaptureFailure) as caught:
        asyncio.run(
            module.run_capture(
                case_id="capture-case",
                now=lambda: datetime(2026, 10, 26, tzinfo=UTC),
                store_observations=AsyncMock(),
                store_revisions=AsyncMock(),
                messages=browser(),
                send=send,
                connect_transcriber=connect,
            )
        )
    assert caught.value.code == "notConfigured"
    assert sent == []


def test_drain_deadline_is_started_only_after_stop(monkeypatch):
    async def scenario():
        stopping = asyncio.Event()
        slept = []
        yield_to_task = asyncio.sleep

        async def sleep(seconds):
            slept.append(seconds)

        monkeypatch.setattr(module.asyncio, "sleep", sleep)
        task = asyncio.create_task(module._drain_timeout(stopping))
        await yield_to_task(0)
        assert slept == []
        stopping.set()
        with pytest.raises(CaptureFailure) as caught:
            await task
        assert caught.value.code == "providerTimeout"
        assert slept == [10]

    asyncio.run(scenario())


def opening(*failures, transcriber):
    """Fail to open with each failure in turn, then open `transcriber`; count the attempts."""
    remaining = list(failures)
    attempts = []

    @asynccontextmanager
    async def connect():
        attempts.append(len(attempts) + 1)
        if remaining:
            raise remaining.pop(0)
        yield transcriber

    return connect, attempts


def open_transcriber(*, connect, slept, monkeypatch):
    """Open with retries, recording each wait in `slept` instead of sleeping."""

    async def sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(module.asyncio, "sleep", sleep)

    async def scenario():
        async with AsyncExitStack() as stack:
            return await module._open_transcriber(
                stack=stack, connect_transcriber=connect, capture_id="capture"
            )

    return asyncio.run(scenario())


def test_transient_open_failures_are_retried_with_growing_waits(monkeypatch):
    transcriber = FakeTranscriber()
    connect, attempts = opening(
        CaptureFailure("providerUnavailable"),
        CaptureFailure("providerTimeout"),
        transcriber=transcriber,
    )
    slept = []

    assert open_transcriber(connect=connect, slept=slept, monkeypatch=monkeypatch) is transcriber
    assert attempts == [1, 2, 3]
    assert slept == [1, 2]


def test_opening_gives_up_after_three_attempts(monkeypatch):
    connect, attempts = opening(
        *[CaptureFailure("providerUnavailable")] * 3, transcriber=FakeTranscriber()
    )
    slept = []

    with pytest.raises(CaptureFailure) as caught:
        open_transcriber(connect=connect, slept=slept, monkeypatch=monkeypatch)
    assert caught.value.code == "providerUnavailable"
    assert attempts == [1, 2, 3]
    assert slept == [1, 2]


@pytest.mark.parametrize("code", ["notConfigured", "providerAuth", "providerProtocol"])
def test_other_open_failures_are_not_retried(monkeypatch, code):
    connect, attempts = opening(CaptureFailure(code), transcriber=FakeTranscriber())
    slept = []

    with pytest.raises(CaptureFailure) as caught:
        open_transcriber(connect=connect, slept=slept, monkeypatch=monkeypatch)
    assert caught.value.code == code
    assert attempts == [1]
    assert slept == []
