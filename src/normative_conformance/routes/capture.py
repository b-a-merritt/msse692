from pathlib import Path
from typing import Literal

from fastapi import APIRouter
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from fastapi.responses import FileResponse

from normative_conformance.schemas.capture import ErrorMessage
from normative_conformance.schemas.capture import FrameLevelPayload
from normative_conformance.schemas.capture import LevelsMessage
from normative_conformance.schemas.capture import ReadyMessage
from normative_conformance.schemas.capture import StoppedMessage
from normative_conformance.services.capture.levels import SAMPLE_RATE
from normative_conformance.services.capture.levels import FrameLevel
from normative_conformance.services.capture.levels import LevelMeter

router = APIRouter()
STATIC = Path(__file__).parent.parent / "static"


def _levels_message(frames: list[FrameLevel]) -> LevelsMessage:
    return LevelsMessage(
        type="levels",
        frames=[
            FrameLevelPayload(
                start_ms=frame.start_ms,
                end_ms=frame.end_ms,
                dbfs=frame.dbfs,
            )
            for frame in frames
        ],
    )


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
    ],
) -> FileResponse:
    return FileResponse(STATIC / asset, media_type="text/javascript")


@router.websocket("/api/v1/capture/audio")
async def capture_audio(websocket: WebSocket) -> None:
    await websocket.accept()
    meter = LevelMeter()
    try:
        await websocket.send_json(
            ReadyMessage(
                type="ready",
                sample_rate=SAMPLE_RATE,
                encoding="pcm_s16le",
                channels=1,
            )
        )
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return
            pcm = message.get("bytes")
            if pcm is not None:
                if not pcm or len(pcm) > 3200 or len(pcm) % 2:
                    await websocket.send_json(
                        ErrorMessage(
                            type="error",
                            message="Send 1-1600 PCM16 samples per binary message",
                        )
                    )
                    await websocket.close(code=1008)
                    return
                frames = meter.feed(pcm=pcm)
            elif message.get("text") == "stop":
                frames = meter.finish()
                await websocket.send_json(_levels_message(frames))
                await websocket.send_json(StoppedMessage(type="stopped"))
                await websocket.close(code=1000)
                return
            else:
                await websocket.send_json(
                    ErrorMessage(
                        type="error",
                        message="Expected PCM audio or stop",
                    )
                )
                await websocket.close(code=1008)
                return
            if frames:
                await websocket.send_json(_levels_message(frames))
    except WebSocketDisconnect:
        return
