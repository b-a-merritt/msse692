"""Health checks report runtime availability without creating work."""

import sqlite3
from threading import Thread
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from normative_conformance.config import Settings
from normative_conformance.main import create_app


@pytest.fixture
def application(*, tmp_path):
    return create_app(
        settings=Settings(
            app_db_path=tmp_path / "app.sqlite3",
            assessment_queue_path=tmp_path / "queue",
        )
    )


@pytest.fixture
def client(*, application):
    with TestClient(application) as client:
        yield client


def test_liveness_works_before_startup_and_readiness_does_not(*, application, tmp_path):
    client = TestClient(application)
    try:
        live = client.get("/health/live")
        ready = client.get("/health/ready")
    finally:
        client.close()

    assert live.status_code == 200
    assert live.json() == {"status": "live"}
    assert ready.status_code == 503
    assert ready.json()["error"]["code"] == "NOT_READY"
    assert not (tmp_path / "app.sqlite3").exists()
    assert not (tmp_path / "queue").exists()


@pytest.mark.parametrize("endpoint,status", [("live", "live"), ("ready", "ready")])
def test_healthy_response_has_metadata(*, client, endpoint, status):
    response = client.get("/health/" + endpoint)

    assert response.status_code == 200
    assert response.json() == {"status": status}
    assert UUID(response.headers["X-Request-ID"]).version == 4
    assert response.headers["Cache-Control"] == "no-store"
    assert client.app.state.assessment_queue.queue() == []


@pytest.mark.parametrize("attribute", ["engine", "scheduler", "assessment_worker"])
def test_missing_resource_is_not_ready_but_remains_live(*, client, monkeypatch, attribute):
    monkeypatch.setattr(client.app.state, attribute, None)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "NOT_READY"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
    assert client.get("/health/live").json() == {"status": "live"}


def test_dead_worker_is_not_ready(*, client, monkeypatch):
    monkeypatch.setattr(client.app.state, "assessment_worker", Thread())

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["error"]["message"] == "The assessment worker is not running"
    assert client.get("/health/live").status_code == 200


def test_worker_failure_is_not_ready(*, client, monkeypatch):
    monkeypatch.setattr(
        client.app.state.assessment_queue,
        "get",
        Mock(side_effect=sqlite3.OperationalError("private queue details")),
    )
    client.app.state.assessment_worker.join(timeout=5)
    assert not client.app.state.assessment_worker.is_alive()

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "NOT_READY"
    assert client.get("/health/live").status_code == 200


@pytest.mark.parametrize(
    "resource,message",
    [
        ("database", "The application database is unavailable"),
        ("queue", "The assessment queue is unavailable"),
    ],
)
def test_unavailable_storage_returns_safe_error(*, client, monkeypatch, resource, message):
    if resource == "database":
        monkeypatch.setattr(
            client.app.state.engine,
            "connect",
            Mock(side_effect=OperationalError("connect", {}, RuntimeError("private details"))),
        )
    else:
        monkeypatch.setattr(
            client.app.state.assessment_queue,
            "ready_count",
            Mock(side_effect=sqlite3.OperationalError("private details")),
        )

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "NOT_READY",
            "message": message,
            "request_id": response.headers["X-Request-ID"],
        }
    }
    assert client.get("/health/live").status_code == 200


@pytest.mark.parametrize("endpoint,model", [("live", "Liveness"), ("ready", "Readiness")])
def test_openapi_describes_health_responses(*, client, endpoint, model):
    responses = client.get("/openapi.json").json()["paths"]["/health/" + endpoint]["get"][
        "responses"
    ]
    assert responses["200"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/" + model
    )
    assert responses["503"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/ErrorEnvelope"
    )
