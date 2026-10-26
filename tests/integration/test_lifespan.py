"""Startup and shutdown own the database polling worker."""

from datetime import datetime
from datetime import timezone
from threading import Event
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from normative_conformance.config import Settings
from normative_conformance.config import get_settings
from normative_conformance.database import create_database_engine
from normative_conformance.database import initialize_database
from normative_conformance.errors import InvalidModel
from normative_conformance.models.normative_model import NormativeModelVersion
from normative_conformance.models.observation import Observation
from normative_conformance.services.scheduler.run_worker import process_case as processing

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

    def evaluate_case(*, case_id, evaluation_id, session, now, models):
        assert session.get(Observation, (case_id, "chunk")) is not None
        calls.append((case_id, evaluation_id, now()))
        handled.set()
        return []

    monkeypatch.setattr(processing, "evaluate_case", evaluate_case)
    application = create_app(
        settings=Settings(
            _env_file=None,
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
    assert calls[0][0] == "case"
    assert isinstance(calls[0][1], UUID)
    assert calls[0][2] == received_at
    assert application.state.engine is None
    assert application.state.scheduler is None
    assert application.state.assessment_worker is None


def test_invalid_model_stops_startup_before_the_worker_starts(*, tmp_path):
    engine = create_database_engine(path=tmp_path / "app.sqlite3")
    try:
        initialize_database(engine=engine)
        with Session(bind=engine) as session:
            session.add(
                NormativeModelVersion(
                    model_id="harm_phrase",
                    name="Broken",
                    version="2",
                    rules_json='[{"rule_id": "rule", "description": "", "sql": "SELEC 1"}]',
                    parameters_json="{}",
                )
            )
            session.commit()
    finally:
        engine.dispose()
    application = create_app(
        settings=Settings(
            _env_file=None,
            app_db_path=tmp_path / "app.sqlite3",
            log_dir=tmp_path / "logs",
        )
    )

    with pytest.raises(InvalidModel), TestClient(application):
        pytest.fail("Startup should fail when a stored model is invalid")

    assert application.state.engine is None
    assert application.state.assessment_worker is None
