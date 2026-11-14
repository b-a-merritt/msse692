"""Exercise the foreign-request check through FastAPI, the real database, and the lifespan."""

from datetime import UTC
from datetime import datetime

import pytest
from sqlmodel import Session
from sqlmodel import select
from starlette.websockets import WebSocketDisconnect

from conversation_monitor.models.case import ConversationCase
from conversation_monitor.models.observation import Observation


def test_foreign_host_cannot_read_stored_speech(*, open_client):
    with open_client(now=lambda: datetime(2026, 11, 2, tzinfo=UTC)) as client:
        client.post(
            "/api/v1/observations",
            json={
                "case_id": "case",
                "observation_id": "chunk",
                "speaker_id": "A",
                "start_at": "2026-11-02T00:00:00Z",
                "end_at": "2026-11-02T00:00:01Z",
                "transcript": "Private speech",
                "signal_level_min": -30.0,
                "signal_level_avg": -20.0,
                "signal_level_max": -10.0,
            },
        )

        response = client.get(
            "/api/v1/cases/case/observations", headers={"Host": "attacker.example"}
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FOREIGN_REQUEST"
        assert "Private speech" not in response.text


def test_foreign_origin_cannot_create_a_case(*, open_client):
    with open_client(now=lambda: datetime(2026, 11, 2, tzinfo=UTC)) as client:
        response = client.put(
            "/api/v1/cases/case/target",
            json={"target_speaker_id": "A"},
            headers={"Origin": "https://attacker.example"},
        )

        assert response.status_code == 403
        with Session(bind=client.app.state.engine) as session:
            assert session.exec(select(ConversationCase)).all() == []


def test_foreign_origin_cannot_submit_speech(*, open_client):
    with open_client(now=lambda: datetime(2026, 11, 2, tzinfo=UTC)) as client:
        response = client.post(
            "/api/v1/observations",
            json={
                "case_id": "case",
                "observation_id": "chunk",
                "speaker_id": "A",
                "start_at": "2026-11-02T00:00:00Z",
                "end_at": "2026-11-02T00:00:01Z",
                "transcript": "Injected speech",
                "signal_level_min": -30.0,
                "signal_level_avg": -20.0,
                "signal_level_max": -10.0,
            },
            headers={"Origin": "https://attacker.example"},
        )

        assert response.status_code == 403
        with Session(bind=client.app.state.engine) as session:
            assert session.exec(select(Observation)).all() == []


def test_foreign_origin_cannot_mark_interventions_delivered(*, open_client):
    with open_client(now=lambda: datetime(2026, 11, 2, tzinfo=UTC)) as client:
        response = client.post(
            "/api/v1/cases/case/interventions/deliver",
            headers={"Origin": "https://attacker.example"},
        )

        assert response.status_code == 403


def test_capture_page_origin_can_create_its_case(*, open_client):
    with open_client(now=lambda: datetime(2026, 11, 2, tzinfo=UTC)) as client:
        response = client.put(
            "/api/v1/cases/case/target",
            json={"target_speaker_order": 1},
            headers={"Origin": "http://testserver"},
        )

        assert response.status_code == 200


def test_foreign_origin_cannot_open_capture(*, open_client):
    with open_client(now=lambda: datetime(2026, 11, 2, tzinfo=UTC)) as client:
        client.put("/api/v1/cases/case/target", json={"target_speaker_order": 1})

        with (
            pytest.raises(WebSocketDisconnect) as caught,
            client.websocket_connect(
                "/api/v1/capture/audio?case_id=case",
                headers={"Origin": "https://attacker.example"},
            ),
        ):
            pass

        assert caught.value.code == 1008


def test_foreign_host_cannot_open_capture(*, open_client):
    with open_client(now=lambda: datetime(2026, 11, 2, tzinfo=UTC)) as client:
        client.put("/api/v1/cases/case/target", json={"target_speaker_order": 1})

        with (
            pytest.raises(WebSocketDisconnect) as caught,
            client.websocket_connect(
                "/api/v1/capture/audio?case_id=case",
                headers={"Host": "attacker.example"},
            ),
        ):
            pass

        assert caught.value.code == 1008


def test_capture_page_origin_can_open_capture(*, open_client):
    with open_client(now=lambda: datetime(2026, 11, 2, tzinfo=UTC)) as client:
        client.put("/api/v1/cases/case/target", json={"target_speaker_order": 1})

        with client.websocket_connect(
            "/api/v1/capture/audio?case_id=case",
            headers={"Origin": "http://testserver"},
        ) as socket:
            # No transcription key is configured, so an accepted socket reports that.
            assert socket.receive_json()["code"] == "notConfigured"
