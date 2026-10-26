import asyncio
from contextlib import nullcontext
from typing import get_args
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
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

    async def run_capture(
        *, case_id, messages, send, connect_transcriber, now, store_observations, store_revisions
    ):
        calls["case_id"] = case_id
        calls["messages"] = [await anext(messages), await anext(messages)]
        calls["connect"] = connect_transcriber
        await send({"type": "stopped"})

    monkeypatch.setattr(capture, "run_capture", run_capture)
    asyncio.run(capture.capture_audio(websocket, case=Mock(case_id="capture-case")))
    websocket.accept.assert_awaited_once()
    assert calls["case_id"] == "capture-case"
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
    asyncio.run(capture.capture_audio(websocket, case=Mock(case_id="capture-case")))
    websocket.send_json.assert_awaited_once_with(
        {"type": "error", "code": code, "message": capture.ERROR_MESSAGES[code]}
    )
    websocket.close.assert_awaited_once_with(code=close_code)


def test_every_failure_code_has_fixed_text():
    assert set(capture.ERROR_MESSAGES) == set(get_args(CaptureErrorCode))


@pytest.mark.parametrize("received", [{"type": "websocket.disconnect"}, WebSocketDisconnect(1006)])
def test_browser_disconnect_ends_quietly(monkeypatch, received):
    websocket = socket(received)

    async def run_capture(
        *, case_id, messages, send, connect_transcriber, now, store_observations, store_revisions
    ):
        await anext(messages)

    monkeypatch.setattr(capture, "run_capture", run_capture)
    asyncio.run(capture.capture_audio(websocket, case=Mock(case_id="capture-case")))
    websocket.send_json.assert_not_awaited()
    websocket.close.assert_not_awaited()


def test_disconnect_while_sending_ends_quietly(monkeypatch):
    websocket = socket()
    websocket.send_json.side_effect = WebSocketDisconnect(1006)

    async def run_capture(
        *, case_id, messages, send, connect_transcriber, now, store_observations, store_revisions
    ):
        await send({"type": "stopped"})

    monkeypatch.setattr(capture, "run_capture", run_capture)
    asyncio.run(capture.capture_audio(websocket, case=Mock(case_id="capture-case")))
    websocket.close.assert_not_awaited()


def test_capture_case_lookup_closes_its_session(monkeypatch):
    websocket = socket()
    session = Mock()
    context = MagicMock()
    context.__enter__.return_value = session
    monkeypatch.setattr(capture, "read_session", Mock(return_value=context))
    record = Mock(case_id="configured-case")
    lookup = Mock(return_value=record)
    monkeypatch.setattr(capture, "get_case", lookup)

    assert capture.get_capture_case(websocket, case_id="configured-case") is record
    lookup.assert_called_once_with(case_id="configured-case", session=session)
    context.__exit__.assert_called_once()


@pytest.mark.parametrize(
    "failure,code",
    [(capture.NotFound("missing"), 1008), (capture.SQLAlchemyError("private details"), 1011)],
)
def test_capture_case_lookup_rejects_missing_or_unavailable_storage(monkeypatch, failure, code):
    websocket = socket()
    monkeypatch.setattr(capture, "read_session", lambda **kwargs: nullcontext(Mock()))
    monkeypatch.setattr(capture, "get_case", Mock(side_effect=failure))
    with pytest.raises(capture.WebSocketException) as caught:
        capture.get_capture_case(websocket, case_id="requested-case")
    assert caught.value.code == code
    assert "private details" not in caught.value.reason


def test_capture_case_lookup_rejects_uninitialized_storage():
    websocket = socket()
    websocket.app.state.engine = None
    with pytest.raises(capture.WebSocketException) as caught:
        capture.get_capture_case(websocket, case_id="requested-case")
    assert caught.value.code == 1011


def test_capture_passes_storage_work_to_threadpool(monkeypatch):
    websocket = socket()
    rows = []
    threadpool = AsyncMock()
    monkeypatch.setattr(capture, "run_in_threadpool", threadpool)

    async def run_capture(*, store_observations, **kwargs):
        await store_observations(rows)

    monkeypatch.setattr(capture, "run_capture", run_capture)
    asyncio.run(capture.capture_audio(websocket, case=Mock(case_id="capture-case")))
    threadpool.assert_awaited_once_with(
        capture.store_observations,
        case_id="capture-case",
        observations=rows,
        engine=websocket.app.state.engine,
        now=websocket.app.state.clock,
        scheduler=websocket.app.state.scheduler,
    )


def test_capture_passes_revision_storage_to_threadpool(monkeypatch):
    websocket = socket()
    replacements = []
    threadpool = AsyncMock()
    monkeypatch.setattr(capture, "run_in_threadpool", threadpool)

    async def run_capture(*, store_revisions, **kwargs):
        await store_revisions(replacements)

    monkeypatch.setattr(capture, "run_capture", run_capture)
    asyncio.run(capture.capture_audio(websocket, case=Mock(case_id="capture-case")))
    threadpool.assert_awaited_once_with(
        capture.store_revisions,
        case_id="capture-case",
        replacements=replacements,
        engine=websocket.app.state.engine,
        now=websocket.app.state.clock,
    )
