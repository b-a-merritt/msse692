import asyncio
import logging
from collections.abc import AsyncIterator
from collections.abc import Awaitable
from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from normative_conformance.errors import CaptureDisconnected
from normative_conformance.errors import CaptureFailure
from normative_conformance.schemas.capture import FrameLevelPayload
from normative_conformance.schemas.capture import LevelsMessage
from normative_conformance.schemas.capture import OutgoingMessage
from normative_conformance.schemas.capture import ReadyMessage
from normative_conformance.schemas.capture import StoppedMessage
from normative_conformance.schemas.capture import TranscriptMessage
from normative_conformance.schemas.capture import WordPayload
from normative_conformance.schemas.internal import Clock
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.schemas.observation import ObservationReplacement
from normative_conformance.services.capture.levels import SAMPLE_RATE
from normative_conformance.services.capture.levels import FrameLevel
from normative_conformance.services.capture.levels import LevelMeter
from normative_conformance.services.capture.observations import build_observations
from normative_conformance.services.capture.pcm import PCMBuffer
from normative_conformance.services.capture.transcriber import ConnectTranscriber
from normative_conformance.services.capture.transcriber import SpeakerRevised
from normative_conformance.services.capture.transcriber import Transcriber
from normative_conformance.services.capture.transcriber import TurnUpdate
from normative_conformance.services.capture.transcriber import Word

logger = logging.getLogger(__name__)

DRAIN_TIMEOUT = 10
BrowserMessage = bytes | str
Send = Callable[[OutgoingMessage], Awaitable[None]]
StoreObservations = Callable[[list[ObservationInput]], Awaitable[None]]
StoreRevisions = Callable[[list[ObservationReplacement]], Awaitable[None]]


async def run_capture(
    *,
    case_id: str,
    messages: AsyncIterator[BrowserMessage],
    send: Send,
    connect_transcriber: ConnectTranscriber,
    now: Clock,
    store_observations: StoreObservations,
    store_revisions: StoreRevisions,
) -> None:
    """Stream browser PCM to a transcriber and report levels and transcripts until `stopped`.

    Raises `CaptureFailure` or `CaptureDisconnected` when capture ends early.
    """
    capture_id = uuid4().hex
    logger.info(
        "Capture connected; opening transcription session",
        extra={"event": "capture.connected", "capture_id": capture_id, "case_id": case_id},
    )
    try:
        async with connect_transcriber() as transcriber:
            started_at = now()
            logger.info(
                "Transcription session ready",
                extra={
                    "event": "capture.provider_ready",
                    "capture_id": capture_id,
                    "provider_session_id": transcriber.session_id,
                    "case_id": case_id,
                    "speech_model": transcriber.speech_model,
                    "sample_rate": SAMPLE_RATE,
                },
            )
            await send(
                ReadyMessage(
                    type="ready",
                    case_id=case_id,
                    sample_rate=SAMPLE_RATE,
                    encoding="pcm_s16le",
                    channels=1,
                    session_id=transcriber.session_id,
                    speech_model=transcriber.speech_model,
                )
            )
            await _stream(
                messages=messages,
                send=send,
                transcriber=transcriber,
                capture_id=capture_id,
                case_id=case_id,
                started_at=started_at,
                store_observations=store_observations,
                store_revisions=store_revisions,
            )
        await send(StoppedMessage(type="stopped"))
    except CaptureDisconnected:
        logger.warning(
            "Browser disconnected before capture completed",
            extra={"event": "capture.disconnected", "capture_id": capture_id},
        )
        raise
    except CaptureFailure as error:
        logger.warning(
            "Capture failed",
            extra={"event": "capture.failed", "capture_id": capture_id, "error_code": error.code},
        )
        raise
    logger.info(
        "Capture completed; transcription session terminated",
        extra={"event": "capture.completed", "capture_id": capture_id},
    )


def _levels_message(frames: list[FrameLevel]) -> LevelsMessage:
    return LevelsMessage(
        type="levels",
        frames=[
            FrameLevelPayload(start_ms=f.start_ms, end_ms=f.end_ms, dbfs=f.dbfs) for f in frames
        ],
    )


def _transcript_message(
    *,
    turn_order: int,
    final: bool,
    revised: bool,
    transcript: str,
    speaker_id: str | None,
    words: tuple[Word, ...],
) -> TranscriptMessage:
    return TranscriptMessage(
        type="transcript",
        turn_order=turn_order,
        final=final,
        revised=revised,
        transcript=transcript,
        speaker_id=speaker_id,
        words=[
            WordPayload(text=w.text, start_ms=w.start_ms, end_ms=w.end_ms, speaker_id=w.speaker_id)
            for w in words
        ],
    )


async def _stream(
    *,
    messages: AsyncIterator[BrowserMessage],
    send: Send,
    transcriber: Transcriber,
    capture_id: str,
    case_id: str,
    started_at: datetime,
    store_observations: StoreObservations,
    store_revisions: StoreRevisions,
) -> None:
    """Finish when the transcriber's events end; any task's failure ends capture."""
    stopping = asyncio.Event()
    frames: list[FrameLevel] = []
    events = asyncio.create_task(
        _events(
            transcriber=transcriber,
            send=send,
            stopping=stopping,
            capture_id=capture_id,
            case_id=case_id,
            started_at=started_at,
            frames=frames,
            store_observations=store_observations,
            store_revisions=store_revisions,
        )
    )
    tasks = {
        events,
        asyncio.create_task(
            _audio(
                messages=messages,
                send=send,
                transcriber=transcriber,
                stopping=stopping,
                capture_id=capture_id,
                frames=frames,
            )
        ),
        asyncio.create_task(_drain_timeout(stopping)),
    }
    pending = tasks
    try:
        while events in pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def _audio(
    *,
    messages: AsyncIterator[BrowserMessage],
    send: Send,
    transcriber: Transcriber,
    stopping: asyncio.Event,
    capture_id: str,
    frames: list[FrameLevel],
) -> None:
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
                        "audio_duration_ms": bytes_sent * 1000 / (SAMPLE_RATE * 2),
                        "packets_sent": packets_sent,
                    },
                )
                next_progress_at = bytes_sent + SAMPLE_RATE * 2 * 5
        if not isinstance(message, bytes):
            logger.info(
                "Capture stopping; waiting for final transcripts and speaker revisions",
                extra={
                    "event": "capture.stopping",
                    "capture_id": capture_id,
                    "audio_duration_ms": bytes_sent * 1000 / (SAMPLE_RATE * 2),
                    "packets_sent": packets_sent,
                },
            )
            stopping.set()
            await transcriber.finish()
    if not stopping.is_set():
        raise CaptureDisconnected()


async def _events(
    *,
    transcriber: Transcriber,
    send: Send,
    stopping: asyncio.Event,
    capture_id: str,
    case_id: str,
    started_at: datetime,
    frames: list[FrameLevel],
    store_observations: StoreObservations,
    store_revisions: StoreRevisions,
) -> None:
    last_partial_turn: int | None = None
    observation_ids: dict[int, list[str]] = {}
    async for event in transcriber.events():
        if isinstance(event, TurnUpdate):
            if event.final:
                if event.turn_order in observation_ids:
                    continue
                observations = build_observations(
                    case_id=case_id,
                    session_id=transcriber.session_id,
                    started_at=started_at,
                    frames=frames,
                    turn=event,
                )
                if observations:
                    await store_observations(observations)
                    observation_ids[event.turn_order] = [row.observation_id for row in observations]
            if event.final or event.turn_order != last_partial_turn:
                logger.info(
                    "Final transcript received" if event.final else "Partial transcript received",
                    extra={
                        "event": "capture.transcript_received",
                        "capture_id": capture_id,
                        "turn_order": event.turn_order,
                        "final": event.final,
                        "speaker_id": event.speaker_id,
                        "word_count": len(event.words),
                        "character_count": len(event.transcript),
                    },
                )
                last_partial_turn = event.turn_order
            await send(
                _transcript_message(
                    turn_order=event.turn_order,
                    final=event.final,
                    revised=False,
                    transcript=event.transcript,
                    speaker_id=event.speaker_id,
                    words=event.words,
                )
            )
        elif isinstance(event, SpeakerRevised):
            replacements = []
            for turn in event.turns:
                original_ids = observation_ids.get(turn.turn_order)
                if original_ids is None:
                    raise CaptureFailure("providerProtocol")
                observations = build_observations(
                    case_id=case_id,
                    session_id=transcriber.session_id,
                    started_at=started_at,
                    frames=frames,
                    turn=TurnUpdate(
                        turn_order=turn.turn_order,
                        final=True,
                        speaker_id=turn.speaker_id,
                        transcript=" ".join(w.text for w in turn.words),
                        words=turn.words,
                    ),
                )
                replacements.append(
                    ObservationReplacement(
                        replaced_observation_ids=original_ids, observations=observations
                    )
                )
            await store_revisions(replacements)
            logger.info(
                "Speaker revisions received",
                extra={
                    "event": "capture.speaker_revisions",
                    "capture_id": capture_id,
                    "turn_orders": [turn.turn_order for turn in event.turns],
                },
            )
            for turn in event.turns:
                await send(
                    _transcript_message(
                        turn_order=turn.turn_order,
                        final=True,
                        revised=True,
                        transcript=" ".join(w.text for w in turn.words),
                        speaker_id=turn.speaker_id,
                        words=turn.words,
                    )
                )
        else:
            logger.info(
                "Speech detected by transcription service",
                extra={"event": "capture.speech_started", "capture_id": capture_id},
            )
    if not stopping.is_set():
        raise CaptureFailure("incomplete")


async def _drain_timeout(stopping: asyncio.Event) -> None:
    await stopping.wait()
    await asyncio.sleep(DRAIN_TIMEOUT)
    raise CaptureFailure("providerTimeout")
