import json
from contextlib import contextmanager
from datetime import datetime
from datetime import timezone
from threading import Thread
from unittest.mock import Mock

import pytest
from starlette.websockets import WebSocketDisconnect
from websockets.sync.server import serve

from normative_conformance.clients import assemblyai as module


@contextmanager
def provider_server(handler):
    """Run a local WebSocket transport; the test supplies all provider events."""
    with serve(handler, "127.0.0.1", 0) as server:
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            yield f"ws://127.0.0.1:{server.socket.getsockname()[1]}/v3/ws"
        finally:
            server.shutdown()
            thread.join(timeout=5)


def test_serves_the_capture_page_and_its_javascript(open_client):
    with open_client(now=lambda: datetime(2026, 10, 24, tzinfo=timezone.utc)) as client:
        page = client.get("/capture")
        assert page.status_code == 200
        assert "Start microphone" in page.text
        assert "Live transcript" in page.text
        for path in [
            "/capture/capture.js",
            "/capture/pcm-worklet.js",
            "/capture/capture/levels.js",
            "/capture/capture/session.js",
            "/capture/capture/status.js",
            "/capture/capture/transcript.js",
        ]:
            script = client.get(path)
            assert script.status_code == 200
            assert script.headers["content-type"].startswith("text/javascript")
        assert client.get("/capture/config.py").status_code == 422
        assert client.get("/capture/capture/config.py").status_code == 422


def test_pcm_and_final_revisions_cross_both_websockets(open_client, monkeypatch):
    received = []
    credentials = []

    def provider(socket):
        credentials.append(socket.request.headers["Authorization"])
        socket.send(json.dumps({"type": "Begin", "id": "integration-session"}))
        while True:
            packet = socket.recv(timeout=5)
            received.append(packet)
            if isinstance(packet, bytes):
                socket.send(
                    json.dumps(
                        {
                            "type": "Turn",
                            "turn_order": 0,
                            "end_of_turn": False,
                            "transcript": "Hello",
                            "words": [],
                        }
                    )
                )
            else:
                assert json.loads(packet) == {"type": "Terminate"}
                for event in [
                    {
                        "type": "Turn",
                        "turn_order": 0,
                        "end_of_turn": True,
                        "speaker_label": "A",
                        "transcript": "Hello.",
                        "words": [{"text": "Hello.", "start": 0, "end": 200, "speaker": "A"}],
                    },
                    {
                        "type": "SpeakerRevision",
                        "revisions": [
                            {
                                "turn_order": 0,
                                "speaker_label": "B",
                                "words": [
                                    {"text": "Hello.", "start": 0, "end": 200, "speaker": "B"}
                                ],
                            }
                        ],
                    },
                    {"type": "Termination"},
                ]:
                    socket.send(json.dumps(event))
                return

    with (
        provider_server(provider) as url,
        open_client(now=lambda: datetime(2026, 10, 24, tzinfo=timezone.utc)) as client,
    ):
        monkeypatch.setattr(module, "PROVIDER_URL", url)
        client.app.state.settings.assembly_api_key = "integration-key"
        configured = client.put(
            "/api/v1/cases/capture-case/target", json={"target_speaker_order": 2}
        )
        assert configured.status_code == 200
        with client.websocket_connect("/api/v1/capture/audio?case_id=capture-case") as websocket:
            assert websocket.receive_json() == {
                "type": "ready",
                "case_id": "capture-case",
                "sample_rate": 16000,
                "encoding": "pcm_s16le",
                "channels": 1,
                "session_id": "integration-session",
                "speech_model": "universal-3-6-pro",
            }
            audio = b"\x00\x00" * 3200 + b"\x00\x80" * 80
            for packet in [audio[:3200], audio[3200:6400], audio[6400:]]:
                websocket.send_bytes(packet)
            websocket.send_text("stop")
            messages = []
            while True:
                message = websocket.receive_json()
                messages.append(message)
                if message["type"] == "stopped":
                    break
                assert message["type"] != "error"
            assert messages[-2] == {
                "type": "transcript",
                "turn_order": 0,
                "final": True,
                "revised": True,
                "transcript": "Hello.",
                "speaker_id": "B",
                "words": [{"text": "Hello.", "start_ms": 0, "end_ms": 200, "speaker_id": "B"}],
            }
            frames = [f for m in messages if m["type"] == "levels" for f in m["frames"]]
            assert frames[-1] == {"start_ms": 200, "end_ms": 205, "dbfs": 0}
            assert len(frames) == 11
            with pytest.raises(WebSocketDisconnect) as closed:
                websocket.receive_json()
            assert closed.value.code == 1000
        stored = client.get("/api/v1/cases/capture-case").json()
        assert stored["target_speaker_order"] == 2
        assert stored["target_speaker_id"] is None
        assert client.app.state.assessment_queue.queue() == []
    assert credentials == ["integration-key"]
    assert b"".join(packet for packet in received if isinstance(packet, bytes)) == audio
    assert received[-1] == module.TERMINATE


def test_malformed_pcm_closes_both_connections(open_client, monkeypatch):
    received = []

    def provider(socket):
        socket.send('{"type":"Begin","id":"s"}')
        received.append(socket.recv(timeout=5))

    with (
        provider_server(provider) as url,
        open_client(now=lambda: datetime(2026, 10, 24, tzinfo=timezone.utc)) as client,
    ):
        monkeypatch.setattr(module, "PROVIDER_URL", url)
        client.app.state.settings.assembly_api_key = "integration-key"
        configured = client.put(
            "/api/v1/cases/capture-case/target", json={"target_speaker_order": 2}
        )
        assert configured.status_code == 200
        with client.websocket_connect("/api/v1/capture/audio?case_id=capture-case") as websocket:
            websocket.receive_json()
            websocket.send_bytes(b"\x00")
            assert websocket.receive_json()["code"] == "invalidAudio"
            with pytest.raises(WebSocketDisconnect) as closed:
                websocket.receive_json()
            assert closed.value.code == 1008
    assert received == [module.TERMINATE]


def test_provider_disconnect_does_not_report_success(open_client, monkeypatch):
    def provider(socket):
        socket.send('{"type":"Begin","id":"s"}')
        socket.close()

    with (
        provider_server(provider) as url,
        open_client(now=lambda: datetime(2026, 10, 24, tzinfo=timezone.utc)) as client,
    ):
        monkeypatch.setattr(module, "PROVIDER_URL", url)
        client.app.state.settings.assembly_api_key = "integration-key"
        configured = client.put(
            "/api/v1/cases/capture-case/target", json={"target_speaker_order": 2}
        )
        assert configured.status_code == 200
        with client.websocket_connect("/api/v1/capture/audio?case_id=capture-case") as websocket:
            assert websocket.receive_json()["type"] == "ready"
            assert websocket.receive_json()["code"] == "providerUnavailable"
            with pytest.raises(WebSocketDisconnect) as closed:
                websocket.receive_json()
            assert closed.value.code == 1011


def test_missing_key_is_reported_on_capture_without_breaking_http(open_client):
    with open_client(now=lambda: datetime(2026, 10, 24, tzinfo=timezone.utc)) as client:
        client.app.state.settings.assembly_api_key = ""
        assert client.get("/health/live").status_code == 200
        configured = client.put(
            "/api/v1/cases/capture-case/target", json={"target_speaker_order": 2}
        )
        assert configured.status_code == 200
        with client.websocket_connect("/api/v1/capture/audio?case_id=capture-case") as websocket:
            assert websocket.receive_json()["code"] == "notConfigured"
            with pytest.raises(WebSocketDisconnect) as closed:
                websocket.receive_json()
            assert closed.value.code == 1011


@pytest.mark.parametrize("query", ["", "?case_id=", "?case_id=missing", "?case_id=bad/name"])
def test_capture_requires_an_existing_case_before_opening_provider(open_client, monkeypatch, query):
    connect = Mock(side_effect=AssertionError("Provider must not be opened"))
    monkeypatch.setattr(module, "connect_transcriber", connect)
    with open_client(now=lambda: datetime(2026, 10, 26, tzinfo=timezone.utc)) as client:
        with (
            pytest.raises(WebSocketDisconnect) as closed,
            client.websocket_connect(f"/api/v1/capture/audio{query}"),
        ):
            pass
        assert closed.value.code == 1008
    connect.assert_not_called()
