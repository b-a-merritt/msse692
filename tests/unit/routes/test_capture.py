import asyncio
from typing import get_args
from unittest.mock import AsyncMock
from unittest.mock import Mock

import pytest
from fastapi import WebSocketDisconnect

from normative_conformance.clients import assemblyai
from normative_conformance.errors import CaptureFailure
from normative_conformance.routes import capture
from normative_conformance.schemas.capture import CaptureErrorCode


def test_page_and_script_responses_use_packaged_assets(monkeypatch):
    response = Mock()
    monkeypatch.setattr(capture, "FileResponse", response)
    assert capture.capture_page() is response.return_value
    response.assert_called_with(capture.STATIC / "capture.html")
    assert capture.capture_asset("pcm-worklet.js") is response.return_value
    response.assert_called_with(capture.STATIC / "pcm-worklet.js", media_type="text/javascript")


def socket(*received):
    websocket = AsyncMock()
    websocket.app = Mock()
    websocket.app.state.settings.assembly_api_key = "unit-key"
    websocket.receive.side_effect = received
    return websocket


def test_route_relays_browser_frames_and_closes_after_success(monkeypatch):
    websocket = socket(
        {"type": "websocket.receive", "bytes": b"\x00\x00"},
        {"type": "websocket.receive", "text": "stop"},
    )
    calls = {}

    async def run_capture(*, messages, send, connect_transcriber):
        calls["messages"] = [await anext(messages), await anext(messages)]
        calls["connect"] = connect_transcriber
        await send({"type": "stopped"})

    monkeypatch.setattr(capture, "run_capture", run_capture)
    asyncio.run(capture.capture_audio(websocket))
    websocket.accept.assert_awaited_once()
    assert calls["messages"] == [b"\x00\x00", "stop"]
    assert calls["connect"].func is assemblyai.connect_transcriber
    assert calls["connect"].keywords == {"api_key": "unit-key"}
    websocket.send_json.assert_awaited_once_with({"type": "stopped"})
    websocket.close.assert_awaited_once_with(code=1000)


@pytest.mark.parametrize("code,close_code", [("invalidAudio", 1008), ("providerAuth", 1011)])
def test_failure_sends_fixed_text_and_closes(monkeypatch, code, close_code):
    websocket = socket()

    async def run_capture(**kwargs):
        raise CaptureFailure(code)

    monkeypatch.setattr(capture, "run_capture", run_capture)
    asyncio.run(capture.capture_audio(websocket))
    websocket.send_json.assert_awaited_once_with(
        {"type": "error", "code": code, "message": capture.ERROR_MESSAGES[code]}
    )
    websocket.close.assert_awaited_once_with(code=close_code)


def test_every_failure_code_has_fixed_text():
    assert set(capture.ERROR_MESSAGES) == set(get_args(CaptureErrorCode))


@pytest.mark.parametrize("received", [{"type": "websocket.disconnect"}, WebSocketDisconnect(1006)])
def test_browser_disconnect_ends_quietly(monkeypatch, received):
    websocket = socket(received)

    async def run_capture(*, messages, send, connect_transcriber):
        await anext(messages)

    monkeypatch.setattr(capture, "run_capture", run_capture)
    asyncio.run(capture.capture_audio(websocket))
    websocket.send_json.assert_not_awaited()
    websocket.close.assert_not_awaited()


def test_disconnect_while_sending_ends_quietly(monkeypatch):
    websocket = socket()
    websocket.send_json.side_effect = WebSocketDisconnect(1006)

    async def run_capture(*, messages, send, connect_transcriber):
        await send({"type": "stopped"})

    monkeypatch.setattr(capture, "run_capture", run_capture)
    asyncio.run(capture.capture_audio(websocket))
    websocket.close.assert_not_awaited()
