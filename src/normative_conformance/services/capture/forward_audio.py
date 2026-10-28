import asyncio
import logging
from collections.abc import AsyncIterator

from normative_conformance.errors import CaptureDisconnected
from normative_conformance.errors import CaptureFailure
from normative_conformance.schemas.capture import FrameLevelPayload
from normative_conformance.schemas.capture import LevelsMessage
from normative_conformance.schemas.capture import Send
from normative_conformance.services.capture.levels import SAMPLE_RATE
from normative_conformance.services.capture.levels import FrameLevel
from normative_conformance.services.capture.levels import LevelMeter
from normative_conformance.services.capture.pcm import BYTES_PER_SAMPLE
from normative_conformance.services.capture.pcm import PCMBuffer
from normative_conformance.services.capture.transcriber import Transcriber

logger = logging.getLogger(__name__)

BrowserMessage = bytes | str


async def forward_audio(
    *,
    messages: AsyncIterator[BrowserMessage],
    send: Send,
    transcriber: Transcriber,
    stopping: asyncio.Event,
    capture_id: str,
    frames: list[FrameLevel],
) -> None:
    """Forward browser PCM to the transcriber and report its levels until the browser stops.

    Measured frames are appended to `frames`. Raises `CaptureFailure` for invalid input and
    `CaptureDisconnected` when the browser leaves before stopping.
    """
    meter = LevelMeter()
    buffer = PCMBuffer()
    bytes_sent = 0
    packets_sent = 0
    next_progress_at = 0
    async for message in messages:
        if stopping.is_set():
            raise CaptureFailure("invalidAudio")
        try:
            if isinstance(message, bytes):
                packet = buffer.feed(message)
                measured = meter.feed(pcm=message)
            elif message == "stop":
                packet = buffer.finish()
                measured = meter.finish()
            else:
                raise ValueError("Expected PCM or stop")
        except ValueError as error:
            raise CaptureFailure("invalidAudio") from error
        frames.extend(measured)
        if measured:
            await send(_levels_message(measured))
        if packet:
            await transcriber.send_audio(packet)
            bytes_sent += len(packet)
            packets_sent += 1
            # Report the first packet, then every five seconds of forwarded audio.
            if bytes_sent >= next_progress_at:
                logger.info(
                    "Audio forwarded to transcription service",
                    extra={
                        "event": "capture.audio_forwarded",
                        "capture_id": capture_id,
                        "audio_duration_ms": _audio_ms(bytes_sent),
                        "packets_sent": packets_sent,
                    },
                )
                next_progress_at = bytes_sent + SAMPLE_RATE * BYTES_PER_SAMPLE * 5
        if not isinstance(message, bytes):
            logger.info(
                "Capture stopping; waiting for final transcripts and speaker revisions",
                extra={
                    "event": "capture.stopping",
                    "capture_id": capture_id,
                    "audio_duration_ms": _audio_ms(bytes_sent),
                    "packets_sent": packets_sent,
                },
            )
            stopping.set()
            await transcriber.finish()
    if not stopping.is_set():
        raise CaptureDisconnected()


def _levels_message(frames: list[FrameLevel]) -> LevelsMessage:
    return LevelsMessage(
        type="levels",
        frames=[
            FrameLevelPayload(start_ms=f.start_ms, end_ms=f.end_ms, dbfs=f.dbfs) for f in frames
        ],
    )


def _audio_ms(byte_count: int) -> float:
    return byte_count * 1000 / (SAMPLE_RATE * BYTES_PER_SAMPLE)
