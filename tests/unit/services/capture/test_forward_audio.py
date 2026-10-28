import asyncio
import logging

import pytest

from normative_conformance.errors import CaptureDisconnected
from normative_conformance.errors import CaptureFailure
from normative_conformance.services.capture import forward_audio as module
from normative_conformance.services.capture.levels import FrameLevel


class FakeTranscriber:
    """Record forwarded audio and finish requests."""

    def __init__(self):
        self.audio = []
        self.finished = 0

    async def send_audio(self, pcm):
        self.audio.append(pcm)

    async def finish(self):
        self.finished += 1


async def browser(*messages):
    for message in messages:
        yield message


def test_forwards_audio_and_reports_levels_until_stop():
    transcriber = FakeTranscriber()
    stopping = asyncio.Event()
    frames = []
    sent = []

    async def send(message):
        sent.append(message)

    audio = b"\x00\x00" * 1600 + b"\x00\x80" * 80
    asyncio.run(
        module.forward_audio(
            messages=browser(audio[:3200], audio[3200:], "stop"),
            send=send,
            transcriber=transcriber,
            stopping=stopping,
            capture_id="capture",
            frames=frames,
        )
    )

    assert b"".join(transcriber.audio) == audio
    assert transcriber.finished == 1
    assert stopping.is_set()
    assert frames == [
        FrameLevel(start_ms=start, end_ms=start + 20, dbfs=-120) for start in [0, 20, 40, 60, 80]
    ] + [FrameLevel(start_ms=100, end_ms=105, dbfs=0)]
    assert [f for m in sent for f in m["frames"]] == [
        {"start_ms": f.start_ms, "end_ms": f.end_ms, "dbfs": f.dbfs} for f in frames
    ]


@pytest.mark.parametrize("message", [b"", b"\x00", b"\x00" * 3202, "bad command"])
def test_invalid_browser_input_is_rejected(message):
    transcriber = FakeTranscriber()

    async def send(message):
        pass

    with pytest.raises(CaptureFailure) as caught:
        asyncio.run(
            module.forward_audio(
                messages=browser(message),
                send=send,
                transcriber=transcriber,
                stopping=asyncio.Event(),
                capture_id="capture",
                frames=[],
            )
        )
    assert caught.value.code == "invalidAudio"
    assert transcriber.finished == 0


def test_input_after_stop_is_rejected():
    async def send(message):
        pass

    with pytest.raises(CaptureFailure) as caught:
        asyncio.run(
            module.forward_audio(
                messages=browser("stop", b"\x00\x00" * 1600),
                send=send,
                transcriber=FakeTranscriber(),
                stopping=asyncio.Event(),
                capture_id="capture",
                frames=[],
            )
        )
    assert caught.value.code == "invalidAudio"


def test_browser_leaving_before_stop_is_a_disconnect():
    async def send(message):
        pass

    with pytest.raises(CaptureDisconnected):
        asyncio.run(
            module.forward_audio(
                messages=browser(b"\x00\x00" * 1600),
                send=send,
                transcriber=FakeTranscriber(),
                stopping=asyncio.Event(),
                capture_id="capture",
                frames=[],
            )
        )


def test_audio_progress_is_periodic_and_stop_reports_total(caplog):
    # Logging cadence is the observable behavior under test, not evidence of routing success.
    caplog.set_level(logging.INFO, logger=module.__name__)
    packet = b"\x00\x00" * 1600  # 100 ms of silence per message.
    transcriber = FakeTranscriber()

    async def send(message):
        pass

    asyncio.run(
        module.forward_audio(
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
