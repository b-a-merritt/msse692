from collections.abc import AsyncIterator
from collections.abc import Iterator
from contextlib import contextmanager
from contextlib import suppress
from functools import partial
from pathlib import Path
from typing import Annotated
from typing import Literal
from typing import cast

from fastapi import APIRouter
from fastapi import Depends
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from fastapi import WebSocketException
from fastapi.responses import FileResponse
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import State

from conversation_monitor.clients import assemblyai
from conversation_monitor.config import Settings
from conversation_monitor.database import read_session
from conversation_monitor.errors import CaptureDisconnected
from conversation_monitor.errors import CaptureFailure
from conversation_monitor.errors import NotFound
from conversation_monitor.routes.dependencies import QueryId
from conversation_monitor.schemas.capture import CaptureErrorCode
from conversation_monitor.schemas.capture import ErrorMessage
from conversation_monitor.schemas.capture import OutgoingMessage
from conversation_monitor.schemas.case import CaseRecord
from conversation_monitor.schemas.internal import Clock
from conversation_monitor.schemas.observation import ObservationInput
from conversation_monitor.schemas.observation import ObservationReplacement
from conversation_monitor.services.capture.forward_audio import BrowserMessage
from conversation_monitor.services.capture.run_capture import run_capture
from conversation_monitor.services.capture.store_observations import store_observations
from conversation_monitor.services.capture.store_revisions import store_revisions
from conversation_monitor.services.case.get_case import get_case

router = APIRouter()
STATIC = Path(__file__).parent.parent / "static"
ERROR_MESSAGES: dict[CaptureErrorCode, str] = {
    "notConfigured": "Set ASSEMBLY_API_KEY on the server to enable transcription.",
    "providerAuth": "AssemblyAI rejected the server credentials.",
    "providerUnavailable": "The transcription connection failed. Capture is incomplete.",
    "providerProtocol": "The transcription service returned invalid data. Capture is incomplete.",
    "providerTimeout": "The transcription service did not respond in time. Capture is incomplete.",
    "invalidAudio": "Send PCM16 packets of 1-1600 samples and record at least 50 ms.",
    "incomplete": "The transcription session ended before capture finished.",
    "storageUnavailable": "Speech or speaker revisions could not be stored. Capture is incomplete.",
    "captureLimit": "Capture reached its time limit. Speech already transcribed is saved.",
    "captureBusy": "Too many captures are running. Stop one and try again.",
}


@contextmanager
def _capture_slot(*, state: State, limit: int) -> Iterator[None]:
    """Hold one of the paid transcription sessions; the event loop serializes this count."""
    if state.active_captures >= limit:
        raise CaptureFailure("captureBusy")
    state.active_captures += 1
    try:
        yield
    finally:
        state.active_captures -= 1


@router.get("/capture", response_class=FileResponse, include_in_schema=False)
def capture_page() -> FileResponse:
    return FileResponse(STATIC / "capture.html")


@router.get("/capture/{asset:path}", response_class=FileResponse, include_in_schema=False)
def capture_asset(
    asset: Literal[
        "capture.js",
        "pcm-worklet.js",
        "capture/levels.js",
        "capture/session.js",
        "capture/status.js",
        "capture/transcript.js",
    ],
) -> FileResponse:
    return FileResponse(STATIC / asset, media_type="text/javascript")


def get_capture_case(
    websocket: WebSocket,
    case_id: QueryId,
) -> CaseRecord:
    """Look up the case in a short transaction before opening transcription."""
    engine = cast(Engine | None, getattr(websocket.app.state, "engine", None))
    if engine is None:
        raise WebSocketException(code=1011, reason="Case storage is unavailable")
    try:
        with read_session(engine=engine) as session:
            return get_case(case_id=case_id, session=session)
    except NotFound as error:
        raise WebSocketException(code=1008, reason="Create a case before capture") from error
    except SQLAlchemyError as error:
        raise WebSocketException(code=1011, reason="Case storage is unavailable") from error


@router.websocket("/api/v1/capture/audio")
async def capture_audio(
    websocket: WebSocket, case: Annotated[CaseRecord, Depends(get_capture_case)]
) -> None:
    settings = cast(Settings, websocket.app.state.settings)
    engine = cast(Engine, websocket.app.state.engine)
    clock = cast(Clock, websocket.app.state.clock)
    await websocket.accept()

    async def messages() -> AsyncIterator[BrowserMessage]:
        while True:
            try:
                message = await websocket.receive()
            except WebSocketDisconnect as error:
                raise CaptureDisconnected() from error
            if message["type"] == "websocket.disconnect":
                raise CaptureDisconnected()
            pcm = message.get("bytes")
            yield pcm if pcm is not None else message.get("text") or ""

    async def send(message: OutgoingMessage) -> None:
        try:
            await websocket.send_json(message)
        except WebSocketDisconnect as error:
            raise CaptureDisconnected() from error

    async def store(observations: list[ObservationInput]) -> None:
        await run_in_threadpool(
            store_observations,
            case_id=case.case_id,
            observations=observations,
            engine=engine,
            now=clock,
        )

    async def store_corrections(replacements: list[ObservationReplacement]) -> None:
        await run_in_threadpool(
            store_revisions,
            case_id=case.case_id,
            replacements=replacements,
            engine=engine,
            now=clock,
        )

    try:
        with _capture_slot(state=websocket.app.state, limit=settings.capture_max_connections):
            await run_capture(
                case_id=case.case_id,
                messages=messages(),
                send=send,
                connect_transcriber=partial(
                    assemblyai.connect_transcriber, api_key=settings.assembly_api_key
                ),
                now=clock,
                store_observations=store,
                store_revisions=store_corrections,
                max_seconds=settings.capture_max_seconds,
            )
    except CaptureDisconnected:
        return
    except CaptureFailure as error:
        with suppress(WebSocketDisconnect):
            await websocket.send_json(
                ErrorMessage(type="error", code=error.code, message=ERROR_MESSAGES[error.code])
            )
            await websocket.close(code=1008 if error.code == "invalidAudio" else 1011)
        return
    await websocket.close(code=1000)
