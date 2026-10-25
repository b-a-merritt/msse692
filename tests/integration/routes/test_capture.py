from datetime import datetime
from datetime import timezone

import pytest
from starlette.websockets import WebSocketDisconnect


def test_serves_the_capture_page_and_its_javascript(open_client):
    with open_client(now=lambda: datetime(2026, 10, 24, tzinfo=timezone.utc)) as client:
        page = client.get("/capture")
        assert page.status_code == 200
        assert "Start microphone" in page.text
        for path in [
            "/capture/capture.js",
            "/capture/pcm-worklet.js",
            "/capture/capture/levels.js",
            "/capture/capture/session.js",
            "/capture/capture/status.js",
        ]:
            script = client.get(path)
            assert script.status_code == 200
            assert script.headers["content-type"].startswith("text/javascript")
        assert client.get("/capture/config.py").status_code == 422
        assert client.get("/capture/capture/config.py").status_code == 422


def test_pcm_websocket_measures_frames_and_flushes_tail(open_client):
    with open_client(now=lambda: datetime(2026, 10, 24, tzinfo=timezone.utc)) as client:
        with client.websocket_connect("/api/v1/capture/audio") as websocket:
            assert websocket.receive_json() == {
                "type": "ready",
                "sample_rate": 16000,
                "encoding": "pcm_s16le",
                "channels": 1,
            }
            websocket.send_bytes(b"\x00\x00" * 1600)
            assert websocket.receive_json() == {
                "type": "levels",
                "frames": [
                    {"start_ms": start, "end_ms": start + 20, "dbfs": -120}
                    for start in [0, 20, 40, 60, 80]
                ],
            }
            websocket.send_bytes(b"\x00\x80" * 80)
            websocket.send_text("stop")
            assert websocket.receive_json() == {
                "type": "levels",
                "frames": [{"start_ms": 100, "end_ms": 105, "dbfs": 0}],
            }
            assert websocket.receive_json() == {"type": "stopped"}
            with pytest.raises(WebSocketDisconnect) as closed:
                websocket.receive_json()
            assert closed.value.code == 1000
        assert client.app.state.assessment_queue.queue() == []


def test_malformed_pcm_closes_the_connection(open_client):
    with (
        open_client(now=lambda: datetime(2026, 10, 24, tzinfo=timezone.utc)) as client,
        client.websocket_connect("/api/v1/capture/audio") as websocket,
    ):
        websocket.receive_json()
        websocket.send_bytes(b"\x00")
        assert websocket.receive_json()["type"] == "error"
        with pytest.raises(WebSocketDisconnect) as closed:
            websocket.receive_json()
        assert closed.value.code == 1008
