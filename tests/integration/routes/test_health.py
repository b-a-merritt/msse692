"""Health checks report runtime availability without creating work."""

from unittest.mock import Mock
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from normative_conformance.config import Settings
from normative_conformance.config import get_settings

# Default ASGI construction must not load a developer's local dotenv file.
with patch.dict(Settings.model_config, {"env_file": None}):
    from normative_conformance.main import create_app
get_settings.cache_clear()


@pytest.fixture
def application(*, tmp_path):
    return create_app(
        settings=Settings(
            _env_file=None,
            type_safe_api_key="integration-key",
            app_db_path=tmp_path / "app.sqlite3",
            log_dir=tmp_path / "logs",
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


@pytest.mark.parametrize("endpoint,status", [("live", "live"), ("ready", "ready")])
def test_healthy_response_has_metadata(*, client, endpoint, status):
    response = client.get("/health/" + endpoint)

    assert response.status_code == 200
    assert response.json() == {"status": status}
    assert UUID(response.headers["X-Request-ID"]).version == 4
    assert response.headers["Cache-Control"] == "no-store"


def test_unavailable_storage_returns_safe_error(*, client, monkeypatch):
    monkeypatch.setattr(
        client.app.state.engine,
        "connect",
        Mock(side_effect=OperationalError("connect", {}, RuntimeError("private details"))),
    )

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "NOT_READY",
            "message": "The application database is unavailable",
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
