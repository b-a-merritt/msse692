"""Exercise ingestion through FastAPI with the real database and lifespan."""

import sqlite3
from unittest.mock import Mock
from uuid import UUID

import pytest
from sqlalchemy.exc import OperationalError
from sqlmodel import Session
from sqlmodel import select

from normative_conformance.models.assessment import Assessment
from normative_conformance.models.case import CaseLog
from normative_conformance.models.observation import Observation


def test_ingestion_returns_committed_observation_and_requests_assessment(
    *, client, observation_data, received_at
):
    response = client.post("/api/v1/observations", json=observation_data)

    assert response.status_code == 202
    assert response.json() == observation_data | {
        "start_at": "2026-09-26T09:00:00.123456Z",
        "end_at": "2026-09-26T09:00:01.654321Z",
        "received_at": received_at.isoformat().replace("+00:00", "Z"),
        "sequence": 1,
    }
    assert UUID(response.headers["X-Request-ID"])
    assert response.headers["Cache-Control"] == "no-store"
    with Session(bind=client.app.state.engine) as session:
        assert session.get(CaseLog, "case") is not None
        stored = session.get(Observation, ("case", "chunk"))
        assert stored is not None
        assert stored.transcript == observation_data["transcript"]
        assert stored.sequence == response.json()["sequence"]
        assert session.exec(select(Assessment)).all() == []
    task = client.app.state.assessment_queue.get(block=False)
    assert task["kind"] == "assess_case"
    assert task["case_id"] == "case"
    assert UUID(task["evaluation_id"]).version == 4


def test_duplicate_submission_returns_conflict(*, client, observation_data):
    assert client.post("/api/v1/observations", json=observation_data).status_code == 202
    response = client.post(
        "/api/v1/observations", json=observation_data | {"transcript": "Replacement"}
    )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "OBSERVATION_EXISTS",
            "message": "An observation with this identity already exists",
            "request_id": response.headers["X-Request-ID"],
        }
    }
    with Session(bind=client.app.state.engine) as session:
        observations = session.exec(select(Observation)).all()
        assert len(observations) == 1
        assert observations[0].transcript == observation_data["transcript"]
    assert client.app.state.assessment_queue.qsize() == 1


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"end_at": "2026-09-26T09:00:00Z"}, id="reversed-interval"),
        pytest.param({"signal_level_avg": -51.0}, id="invalid-signal-order"),
        pytest.param({"signal_level_avg": "-30"}, id="numeric-string"),
        pytest.param({"start_at": "2026-09-26T09:00:00"}, id="naive-timestamp"),
        pytest.param({"transcript": " "}, id="blank-transcript"),
        pytest.param({"sequence": 1}, id="client-sequence"),
        pytest.param({"received_at": "2026-09-26T09:00:02Z"}, id="client-receipt-time"),
    ],
)
def test_invalid_request_creates_no_records(*, client, observation_data, changes):
    response = client.post("/api/v1/observations", json=observation_data | changes)

    assert response.status_code == 422
    assert client.app.state.assessment_queue.empty()
    with Session(bind=client.app.state.engine) as session:
        assert session.exec(select(CaseLog)).all() == []
        assert session.exec(select(Observation)).all() == []


def test_storage_error_returns_safe_message_and_rolls_back(*, client, observation_data):
    with client.app.state.engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE TRIGGER fail_ingestion BEFORE INSERT ON observation
            BEGIN SELECT RAISE(ABORT, 'private database details'); END
        """)
    response = client.post("/api/v1/observations", json=observation_data)

    assert response.status_code == 503
    assert client.app.state.assessment_queue.empty()
    assert response.json() == {
        "error": {
            "code": "STORAGE_UNAVAILABLE",
            "message": "The observation could not be stored",
            "request_id": response.headers["X-Request-ID"],
        }
    }
    with Session(bind=client.app.state.engine) as session:
        assert session.exec(select(CaseLog)).all() == []
        assert session.exec(select(Observation)).all() == []


def test_connection_failure_returns_service_unavailable(*, client, observation_data, monkeypatch):
    monkeypatch.setattr(
        client.app.state.engine,
        "connect",
        Mock(side_effect=OperationalError("connect", {}, RuntimeError("private driver details"))),
    )
    response = client.post("/api/v1/observations", json=observation_data)

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "STORAGE_UNAVAILABLE",
            "message": "The application database is unavailable",
            "request_id": response.headers["X-Request-ID"],
        }
    }


def test_enqueue_failure_returns_committed_observation(*, client, observation_data, monkeypatch):
    queue = client.app.state.assessment_queue
    with monkeypatch.context() as patch:
        patch.setattr(
            queue, "put", Mock(side_effect=sqlite3.OperationalError("private queue details"))
        )
        response = client.post("/api/v1/observations", json=observation_data)

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "ENQUEUE_FAILED"
    assert (
        error["message"] == "The observation was stored but its assessment could not be requested"
    )
    assert error["request_id"] == response.headers["X-Request-ID"]
    assert error["committed_observation"]["case_id"] == "case"
    assert error["committed_observation"]["observation_id"] == "chunk"
    assert error["committed_observation"]["sequence"] == 1
    assert queue.empty()
    with Session(bind=client.app.state.engine) as session:
        assert session.get(CaseLog, "case") is not None
        stored = session.get(Observation, ("case", "chunk"))
        assert stored is not None
        assert stored.sequence == 1

    # Retrying the same observation does not overwrite it or create a work request.
    assert client.post("/api/v1/observations", json=observation_data).status_code == 409
    assert queue.empty()
    next_response = client.post(
        "/api/v1/observations", json=observation_data | {"observation_id": "next"}
    )
    assert next_response.status_code == 202
    assert next_response.json()["sequence"] == 2
    assert queue.qsize() == 1


def test_uninitialized_scheduler_rejects_submission_before_writing(
    *, client, observation_data, monkeypatch
):
    monkeypatch.setattr(client.app.state, "scheduler", None)
    response = client.post("/api/v1/observations", json=observation_data)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "NOT_READY"
    with Session(bind=client.app.state.engine) as session:
        assert session.exec(select(CaseLog)).all() == []
        assert session.exec(select(Observation)).all() == []


def test_openapi_describes_ingestion_responses(*, client):
    responses = client.get("/openapi.json").json()["paths"]["/api/v1/observations"]["post"][
        "responses"
    ]
    assert set(responses) == {"202", "409", "422", "503"}
    assert responses["202"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/ObservationRecord"
    )


def test_stopped_worker_rejects_submission_before_writing(*, client, observation_data):
    client.app.state.scheduler.stopped.set()
    response = client.post("/api/v1/observations", json=observation_data)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "NOT_READY"
    with Session(bind=client.app.state.engine) as session:
        assert session.exec(select(Observation)).all() == []


def test_listing_returns_observations_newest_first(*, client, observation_data):
    client.post("/api/v1/observations", json=observation_data)
    client.post(
        "/api/v1/observations",
        json=observation_data
        | {
            "observation_id": "next",
            "start_at": "2026-09-26T09:01:00Z",
            "end_at": "2026-09-26T09:01:01Z",
        },
    )

    response = client.get("/api/v1/cases/case/observations")

    assert response.status_code == 200
    assert [item["observation_id"] for item in response.json()["items"]] == ["next", "chunk"]


def test_listing_an_unknown_case_returns_empty_items(*, client):
    response = client.get("/api/v1/cases/missing-case/observations")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_openapi_describes_listing_response(*, client):
    responses = client.get("/openapi.json").json()["paths"]["/api/v1/cases/{case_id}/observations"][
        "get"
    ]["responses"]
    assert responses["200"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/ListResponse_ObservationRecord_"
    )
