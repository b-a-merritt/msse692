"""Startup and shutdown own the database polling worker."""

from datetime import datetime
from datetime import timezone
from threading import Event
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import select
from typesafe_sdk import TypeSafeClient

from normative_conformance.config import Settings
from normative_conformance.config import get_settings
from normative_conformance.database import read_session
from normative_conformance.models.observation import Observation
from normative_conformance.services.scheduler.run_worker import run_worker

# Default ASGI construction must not load a developer's local dotenv file.
with patch.dict(Settings.model_config, {"env_file": None}):
    from normative_conformance.main import create_app
get_settings.cache_clear()


def test_lifespan_runs_submitted_assessment_and_closes_resources(*, tmp_path, monkeypatch):
    observation_data = {
        "case_id": "case",
        "observation_id": "chunk",
        "speaker_id": "subject",
        "start_at": "2026-09-26T12:00:00.123456+03:00",
        "end_at": "2026-09-26T12:00:01.654321+03:00",
        "transcript": "  Hello!\n",
        "signal_level_min": -50.0,
        "signal_level_avg": -30.0,
        "signal_level_max": -10.0,
    }
    received_at = datetime(2026, 9, 26, 9, 2, 3, 456_789, tzinfo=timezone.utc)

    handled = Event()
    calls = []

    def process_case(**kwargs):
        with read_session(engine=kwargs["engine"]) as session:
            assert (
                session.exec(
                    select(Observation).where(
                        Observation.case_id == kwargs["case_id"],
                        Observation.observation_id == "chunk",
                    )
                ).one_or_none()
                is not None
            )
        calls.append(kwargs)
        handled.set()

    monkeypatch.setattr(run_worker, "process_case", process_case)
    application = create_app(
        settings=Settings(
            _env_file=None,
            type_safe_api_key="integration-key",
            decision_batch_size=2,
            decision_context_seconds=10,
            app_db_path=tmp_path / "app.sqlite3",
            log_dir=tmp_path / "logs",
        ),
        now=lambda: received_at,
    )
    with TestClient(application) as client:
        worker = application.state.assessment_worker
        assert worker.is_alive()
        assert (
            client.put(
                "/api/v1/cases/case/target", json={"target_speaker_id": "subject"}
            ).status_code
            == 200
        )
        response = client.post("/api/v1/observations", json=observation_data)
        assert response.status_code == 201
        assert handled.wait(timeout=5)

    assert not worker.is_alive()
    assert calls[0]["case_id"] == "case"
    assert isinstance(calls[0]["client"], TypeSafeClient)
    assert calls[0]["batch_size"] == 2
    assert calls[0]["context_seconds"] == 10
    assert calls[0]["now"]() == received_at
    assert application.state.engine is None
    assert application.state.worker_stopped is None
    assert application.state.assessment_worker is None
