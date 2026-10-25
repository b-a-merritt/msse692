from collections.abc import AsyncIterator
from contextlib import suppress
from functools import partial
from pathlib import Path
from typing import Literal
from typing import cast

from fastapi import APIRouter
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from fastapi.responses import FileResponse

from normative_conformance.clients import assemblyai
from normative_conformance.config import Settings
from normative_conformance.errors import CaptureDisconnected
from normative_conformance.errors import CaptureFailure
from normative_conformance.schemas.capture import CaptureErrorCode
from normative_conformance.schemas.capture import ErrorMessage
from normative_conformance.schemas.capture import OutgoingMessage
from normative_conformance.services.capture.run_capture import BrowserMessage
from normative_conformance.services.capture.run_capture import run_capture

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


@router.websocket("/api/v1/capture/audio")
async def capture_audio(websocket: WebSocket) -> None:
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

    try:
        await run_capture(
            messages=messages(),
            send=send,
            connect_transcriber=partial(
                assemblyai.connect_transcriber, api_key=settings.assembly_api_key
            ),
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
