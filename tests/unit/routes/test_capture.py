import asyncio
from unittest.mock import AsyncMock
from unittest.mock import Mock

import pytest
from fastapi import WebSocketDisconnect

from normative_conformance.routes import capture


def test_page_and_script_responses_use_packaged_assets(monkeypatch):
    response = Mock()
    monkeypatch.setattr(capture, "FileResponse", response)
    assert capture.capture_page() is response.return_value
    response.assert_called_with(capture.STATIC / "capture.html")
    assert capture.capture_asset("pcm-worklet.js") is response.return_value
    response.assert_called_with(capture.STATIC / "pcm-worklet.js", media_type="text/javascript")


def test_stream_flushes_partial_frame_before_acknowledging_stop():
    websocket = AsyncMock()
    websocket.receive.side_effect = [
        {"type": "websocket.receive", "bytes": b"\x00\x80" * 320},
        {"type": "websocket.receive", "bytes": b"\x00\x00" * 80},
        {"type": "websocket.receive", "text": "stop"},
    ]
    asyncio.run(capture.capture_audio(websocket))
    websocket.accept.assert_awaited_once()
    assert [call.args[0] for call in websocket.send_json.await_args_list] == [
        {"type": "ready", "sample_rate": 16000, "encoding": "pcm_s16le", "channels": 1},
        {"type": "levels", "frames": [{"start_ms": 0, "end_ms": 20, "dbfs": 0}]},
        {"type": "levels", "frames": [{"start_ms": 20, "end_ms": 25, "dbfs": -120}]},
        {"type": "stopped"},
    ]
    websocket.close.assert_awaited_once_with(code=1000)


@pytest.mark.parametrize(
    "message",
    [
        {"bytes": b""},
        {"bytes": b"\x00"},
        {"bytes": b"\x00" * 3202},
        {"text": "unexpected"},
    ],
)
def test_bad_messages_report_an_error_and_close(message):
    websocket = AsyncMock()
    websocket.receive.return_value = {"type": "websocket.receive", **message}
    asyncio.run(capture.capture_audio(websocket))
    assert websocket.send_json.await_args_list[-1].args[0]["type"] == "error"
    websocket.close.assert_awaited_once_with(code=1008)


@pytest.mark.parametrize("exception", [False, True])
def test_disconnect_has_no_successful_stop_acknowledgment(exception):
    websocket = AsyncMock()
    if exception:
        websocket.receive.side_effect = WebSocketDisconnect(1006)
    else:
        websocket.receive.return_value = {"type": "websocket.disconnect"}
    asyncio.run(capture.capture_audio(websocket))
    assert [call.args[0]["type"] for call in websocket.send_json.await_args_list] == ["ready"]
    websocket.close.assert_not_awaited()
