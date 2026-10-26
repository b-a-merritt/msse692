from collections.abc import AsyncIterator
from contextlib import suppress
from functools import partial
from pathlib import Path
from typing import Annotated
from typing import Literal
from typing import cast

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from fastapi import WebSocketException
from fastapi.responses import FileResponse
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from normative_conformance.clients import assemblyai
from normative_conformance.config import Settings
from normative_conformance.database import read_session
from normative_conformance.errors import CaptureDisconnected
from normative_conformance.errors import CaptureFailure
from normative_conformance.errors import NotFound
from normative_conformance.schemas.capture import CaptureErrorCode
from normative_conformance.schemas.capture import ErrorMessage
from normative_conformance.schemas.capture import OutgoingMessage
from normative_conformance.schemas.case import CaseRecord
from normative_conformance.schemas.internal import Clock
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.services.capture.run_capture import BrowserMessage
from normative_conformance.services.capture.run_capture import run_capture
from normative_conformance.services.capture.store_observations import store_observations
from normative_conformance.services.case.selection import get_case
from normative_conformance.services.scheduler.state import SchedulerState

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
    "storageUnavailable": "Finalized speech could not be stored. Capture is incomplete.",
    "assessmentUnavailable": "Speech was stored but assessment could not be requested.",
}


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
    case_id: Annotated[str, Query(min_length=1, pattern=r"^[^/]+$")],
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
            engine=cast(Engine, websocket.app.state.engine),
            now=cast(Clock, websocket.app.state.clock),
            scheduler=cast(SchedulerState, websocket.app.state.scheduler),
        )

    try:
        await run_capture(
            case_id=case.case_id,
            messages=messages(),
            send=send,
            connect_transcriber=partial(
                assemblyai.connect_transcriber, api_key=settings.assembly_api_key
            ),
            now=cast(Clock, websocket.app.state.clock),
            store_observations=store,
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
