import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from datetime import timezone
from unittest.mock import AsyncMock

import pytest

from normative_conformance.errors import CaptureDisconnected
from normative_conformance.errors import CaptureFailure
from normative_conformance.services.capture import run_capture as module
from normative_conformance.services.capture.levels import FrameLevel
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
    caplog.set_level(logging.INFO, logger=module.__name__)
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
            now=lambda: datetime(2026, 10, 26, tzinfo=timezone.utc),
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
    records = [r for r in caplog.records if r.name == module.__name__]
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


@pytest.mark.parametrize("message", [b"", b"\x00", b"\x00" * 3202, "bad command"])
def test_invalid_browser_input_is_rejected(message):
    transcriber = FakeTranscriber()
    with pytest.raises(CaptureFailure) as caught:
        asyncio.run(
            run(
                case_id="capture-case",
                now=lambda: datetime(2026, 10, 26, tzinfo=timezone.utc),
                store_observations=AsyncMock(),
                store_revisions=AsyncMock(),
                messages=browser(message),
                transcriber=transcriber,
            )
        )
    assert caught.value.code == "invalidAudio"
    assert transcriber.finished == 0


def test_input_after_stop_is_rejected():
    transcriber = FakeTranscriber(end_on_finish=False)
    with pytest.raises(CaptureFailure) as caught:
        asyncio.run(
            run(
                case_id="capture-case",
                now=lambda: datetime(2026, 10, 26, tzinfo=timezone.utc),
                store_observations=AsyncMock(),
                store_revisions=AsyncMock(),
                messages=browser("stop", b"\x00\x00" * 1600),
                transcriber=transcriber,
            )
        )
    assert caught.value.code == "invalidAudio"


def test_browser_leaving_before_stop_is_a_disconnect_without_stopped():
    sent = []

    async def send(message):
        sent.append(message)

    with pytest.raises(CaptureDisconnected):
        asyncio.run(
            module.run_capture(
                case_id="capture-case",
                now=lambda: datetime(2026, 10, 26, tzinfo=timezone.utc),
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
                now=lambda: datetime(2026, 10, 26, tzinfo=timezone.utc),
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
                now=lambda: datetime(2026, 10, 26, tzinfo=timezone.utc),
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


def test_audio_progress_is_periodic_and_stop_reports_total(caplog):
    # Logging cadence is the observable behavior under test, not evidence of routing success.
    caplog.set_level(logging.INFO, logger=module.__name__)
    packet = b"\x00\x00" * 1600  # 100 ms of silence per message.
    transcriber = FakeTranscriber(end_on_finish=False)

    async def send(message):
        pass

    asyncio.run(
        module._audio(
            messages=browser(*[packet] * 60, "stop"),
            send=send,
            transcriber=transcriber,
            stopping=asyncio.Event(),
            capture_id="progress-test",
            frames=[],
        )
    )

    assert b"".join(transcriber.audio) == packet * 60
    records = [r for r in caplog.records if r.name == module.__name__]
    progress = [r for r in records if r.event == "capture.audio_forwarded"]
    assert [r.audio_duration_ms for r in progress] == [100, 5100]
    stopping = next(r for r in records if r.event == "capture.stopping")
    assert stopping.audio_duration_ms == 6000
    assert stopping.packets_sent == 60


def test_partial_log_is_once_per_turn_but_every_update_reaches_browser(caplog):
    # Assert diagnostic throttling directly; all transcript updates must still be delivered.
    caplog.set_level(logging.INFO, logger=module.__name__)
    transcriber = FakeTranscriber()
    transcriber.emit(
        TurnUpdate(turn_order=0, final=False, speaker_id=None, transcript="Hi", words=()),
        TurnUpdate(turn_order=0, final=False, speaker_id=None, transcript="Hi there", words=()),
        TurnUpdate(
            turn_order=0,
            final=True,
            speaker_id=None,
            transcript="Hi there.",
            words=(Word(text="Hi there.", start_ms=0, end_ms=20, speaker_id=None),),
        ),
        TurnUpdate(turn_order=1, final=False, speaker_id=None, transcript="Yes", words=()),
        END,
    )
    sent = []

    async def send(message):
        sent.append(message)

    async def scenario():
        stopping = asyncio.Event()
        stopping.set()
        await module._events(
            transcriber=transcriber,
            send=send,
            stopping=stopping,
            capture_id="partial-test",
            store_observations=AsyncMock(),
            store_revisions=AsyncMock(),
            case_id="capture-case",
            started_at=datetime(2026, 10, 26, tzinfo=timezone.utc),
            frames=[FrameLevel(start_ms=0, end_ms=20, dbfs=-30)],
        )

    asyncio.run(scenario())
    assert [m["transcript"] for m in sent] == ["Hi", "Hi there", "Hi there.", "Yes"]
    records = [r for r in caplog.records if r.name == module.__name__]
    assert [(r.turn_order, r.final) for r in records] == [(0, False), (0, True), (1, False)]


def test_persists_final_turn_once_before_reporting_it_and_stopping():
    final = TurnUpdate(0, True, "A", "Hello", (Word("Hello", 0, 100, "A"),))
    transcriber = FakeTranscriber(on_finish=[final, final])
    sent = []
    saved = []

    async def store(observations):
        saved.extend(observations)

    async def send(message):
        if message["type"] in {"transcript", "stopped"}:
            assert len(saved) == 1
        sent.append(message)

    asyncio.run(
        module.run_capture(
            case_id="capture-case",
            messages=browser(b"\x00\x00" * 1600, "stop"),
            send=send,
            connect_transcriber=connecting(transcriber),
            now=lambda: datetime(2026, 10, 26, tzinfo=timezone.utc),
            store_observations=store,
            store_revisions=AsyncMock(),
        )
    )
    assert sent[-1] == {"type": "stopped"}
    assert saved[0].speaker_id == "A"
    assert saved[0].transcript == "Hello"
    assert saved[0].signal_level_avg == -120
    assert saved[0].start_at == datetime(2026, 10, 26, tzinfo=timezone.utc)


def test_storage_failure_ends_capture_without_claiming_completion():
    final = TurnUpdate(0, True, "A", "Hello", (Word("Hello", 0, 100, "A"),))
    transcriber = FakeTranscriber(on_finish=[final])
    sent = []
    send = AsyncMock(side_effect=lambda message: sent.append(message))
    with pytest.raises(CaptureFailure) as caught:
        asyncio.run(
            module.run_capture(
                case_id="capture-case",
                messages=browser(b"\x00\x00" * 1600, "stop"),
                send=send,
                connect_transcriber=connecting(transcriber),
                now=lambda: datetime(2026, 10, 26, tzinfo=timezone.utc),
                store_observations=AsyncMock(side_effect=CaptureFailure("storageUnavailable")),
                store_revisions=AsyncMock(),
            )
        )
    assert caught.value.code == "storageUnavailable"
    assert not any(m["type"] in {"transcript", "stopped"} for m in sent)


def test_later_final_words_do_not_overwrite_or_represent_unsaved_speech():
    original = TurnUpdate(0, True, "A", "Hello", (Word("Hello", 0, 100, "A"),))
    changed = TurnUpdate(0, True, "B", "Hello", (Word("Hello", 0, 100, "B"),))
    transcriber = FakeTranscriber(on_finish=[original, changed])
    saved = []
    sent = []

    async def store(observations):
        saved.extend(observations)

    async def send(message):
        sent.append(message)

    asyncio.run(
        module.run_capture(
            case_id="capture-case",
            messages=browser(b"\x00\x00" * 1600, "stop"),
            send=send,
            connect_transcriber=connecting(transcriber),
            now=lambda: datetime(2026, 10, 26, tzinfo=timezone.utc),
            store_observations=store,
            store_revisions=AsyncMock(),
        )
    )
    assert [(row.speaker_id, row.transcript) for row in saved] == [("A", "Hello")]
    assert [message["speaker_id"] for message in sent if message["type"] == "transcript"] == ["A"]
    assert sent[-1] == {"type": "stopped"}


def test_revisions_commit_before_revised_messages_and_completion():
    final = TurnUpdate(1, True, "A", "Hello", (Word("Hello", 0, 20, "A"),))
    revision = SpeakerRevised((TurnRevision(1, "B", (Word("Hello", 0, 20, "B"),)),))
    transcriber = FakeTranscriber(on_finish=[final, revision])
    stored = []
    sent = []
    observations = AsyncMock()

    async def store(replacements):
        stored.extend(replacements)

    async def send(message):
        if message.get("revised") or message["type"] == "stopped":
            assert len(stored) == 1
            assert stored[0].observations[0].speaker_id == "B"
        sent.append(message)

    async def scenario():
        await module.run_capture(
            case_id="capture-case",
            messages=browser(b"\x00\x00" * 1600, "stop"),
            send=send,
            connect_transcriber=connecting(transcriber),
            now=lambda: datetime(2026, 10, 26, tzinfo=timezone.utc),
            store_observations=observations,
            store_revisions=store,
        )

    asyncio.run(scenario())
    original_id = observations.await_args.args[0][0].observation_id
    assert stored[0].replaced_observation_ids == [original_id]
    assert sent[-2]["revised"] is True
    assert sent[-1] == {"type": "stopped"}
    observations.assert_awaited_once()


def test_revision_storage_failure_sends_no_revision_or_completion():
    final = TurnUpdate(1, True, "A", "Hello", (Word("Hello", 0, 20, "A"),))
    revision = SpeakerRevised((TurnRevision(1, "B", (Word("Hello", 0, 20, "B"),)),))
    transcriber = FakeTranscriber(on_finish=[final, revision])
    sent = []
    observations = AsyncMock()

    async def send(message):
        sent.append(message)

    with pytest.raises(CaptureFailure) as caught:
        asyncio.run(
            module.run_capture(
                case_id="capture-case",
                messages=browser(b"\x00\x00" * 1600, "stop"),
                send=send,
                connect_transcriber=connecting(transcriber),
                now=lambda: datetime(2026, 10, 26, tzinfo=timezone.utc),
                store_observations=observations,
                store_revisions=AsyncMock(side_effect=CaptureFailure("storageUnavailable")),
            )
        )
    assert caught.value.code == "storageUnavailable"
    assert not any(m.get("revised") or m["type"] == "stopped" for m in sent)
    observations.assert_awaited_once()


def test_successive_revisions_regroup_with_utc_times_and_keep_original_links():
    original = TurnUpdate(
        0, True, "A", "Hello there", (Word("Hello", 0, 40, "A"), Word("there", 40, 100, "A"))
    )
    split = SpeakerRevised(
        (TurnRevision(0, "A", (Word("Hello", 0, 40, "A"), Word("there", 40, 100, None))),)
    )
    merged = SpeakerRevised(
        (TurnRevision(0, "B", (Word("Hello", 0, 40, "B"), Word("there", 40, 100, "B"))),)
    )
    transcriber = FakeTranscriber(on_finish=[original, split, merged])
    originals = []
    revisions = []

    async def store_observations(rows):
        originals.extend(rows)

    async def store_revisions(replacements):
        revisions.extend(replacements)

    asyncio.run(
        module.run_capture(
            case_id="case",
            messages=browser(b"\x00\x00" * 640 + b"\x00\x40" * 960, "stop"),
            send=AsyncMock(),
            connect_transcriber=connecting(transcriber),
            now=lambda: datetime(2026, 10, 26, 12, tzinfo=timezone.utc),
            store_observations=store_observations,
            store_revisions=store_revisions,
        )
    )

    assert len(originals) == 1
    assert [r.replaced_observation_ids for r in revisions] == [[originals[0].observation_id]] * 2
    assert [r.speaker_id for r in revisions[0].observations] == ["A", "PENDING"]
    assert [r.transcript for r in revisions[0].observations] == ["Hello", "there"]
    assert revisions[0].observations[0].signal_level_avg == -120
    assert revisions[0].observations[1].signal_level_avg == pytest.approx(-6.020599913279624)
    assert revisions[0].observations[0].start_at == datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
    assert revisions[0].observations[1].start_at == datetime(
        2026, 10, 26, 12, 0, 0, 40000, tzinfo=timezone.utc
    )
    assert revisions[1].observations[0].end_at == datetime(
        2026, 10, 26, 12, 0, 0, 100000, tzinfo=timezone.utc
    )
    assert [r.transcript for r in revisions[1].observations] == ["Hello there"]
    assert revisions[1].observations[0].signal_level_avg == originals[0].signal_level_avg


def test_revision_without_an_original_turn_cannot_create_unlinked_context():
    revision = SpeakerRevised((TurnRevision(99, "B", (Word("Hello", 0, 20, "B"),)),))
    transcriber = FakeTranscriber(on_finish=[revision])
    store = AsyncMock()
    with pytest.raises(CaptureFailure) as caught:
        asyncio.run(
            module.run_capture(
                case_id="case",
                messages=browser("stop"),
                send=AsyncMock(),
                connect_transcriber=connecting(transcriber),
                now=lambda: datetime(2026, 10, 26, tzinfo=timezone.utc),
                store_observations=AsyncMock(),
                store_revisions=store,
            )
        )
    assert caught.value.code == "providerProtocol"
    store.assert_not_awaited()
