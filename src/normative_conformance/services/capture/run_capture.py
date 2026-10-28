import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from datetime import datetime
from functools import partial
from uuid import uuid4

from normative_conformance.errors import CaptureDisconnected
from normative_conformance.errors import CaptureFailure
from normative_conformance.schemas.capture import ReadyMessage
from normative_conformance.schemas.capture import Send
from normative_conformance.schemas.capture import StoppedMessage
from normative_conformance.schemas.internal import Clock
from normative_conformance.services.capture.forward_audio import BrowserMessage
from normative_conformance.services.capture.forward_audio import forward_audio
from normative_conformance.services.capture.levels import SAMPLE_RATE
from normative_conformance.services.capture.levels import FrameLevel
from normative_conformance.services.capture.observations import build_observations
from normative_conformance.services.capture.record_transcripts import StoreObservations
from normative_conformance.services.capture.record_transcripts import StoreRevisions
from normative_conformance.services.capture.record_transcripts import record_transcripts
from normative_conformance.services.capture.transcriber import ConnectTranscriber
from normative_conformance.services.capture.transcriber import Transcriber

logger = logging.getLogger(__name__)

DRAIN_TIMEOUT = 10
# Waits before each retry to open a session. Nothing is streamed until one opens.
CONNECT_RETRY_DELAYS = (1, 2)
TRANSIENT_FAILURES = {"providerUnavailable", "providerTimeout"}


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
        async with AsyncExitStack() as stack:
            transcriber = await _open_transcriber(
                stack=stack, connect_transcriber=connect_transcriber, capture_id=capture_id
            )
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


async def _open_transcriber(
    *, stack: AsyncExitStack, connect_transcriber: ConnectTranscriber, capture_id: str
) -> Transcriber:
    """Open a session, retrying while the provider is unavailable or slow to respond."""
    for attempt, delay in enumerate(CONNECT_RETRY_DELAYS, start=1):
        try:
            return await stack.enter_async_context(connect_transcriber())
        except CaptureFailure as error:
            if error.code not in TRANSIENT_FAILURES:
                raise
            logger.warning(
                "Transcription session failed to open; retrying",
                extra={
                    "event": "capture.provider_retry",
                    "capture_id": capture_id,
                    "attempt": attempt,
                    "error_code": error.code,
                },
            )
            await asyncio.sleep(delay)
    return await stack.enter_async_context(connect_transcriber())


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
        record_transcripts(
            transcriber=transcriber,
            build=partial(
                build_observations,
                case_id=case_id,
                session_id=transcriber.session_id,
                started_at=started_at,
                frames=frames,
            ),
            send=send,
            stopping=stopping,
            capture_id=capture_id,
            store_observations=store_observations,
            store_revisions=store_revisions,
        )
    )
    tasks = {
        events,
        asyncio.create_task(
            forward_audio(
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


async def _drain_timeout(stopping: asyncio.Event) -> None:
    await stopping.wait()
    await asyncio.sleep(DRAIN_TIMEOUT)
    raise CaptureFailure("providerTimeout")
