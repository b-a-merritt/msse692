"""Manage an HTTP client's resources; callers supply the clock and subject."""

from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from normative_conformance.config import Settings
from normative_conformance.main import create_app


@pytest.fixture
def open_client(*, tmp_path, monkeypatch):
    def idle_worker(*, scheduler, engine, now, intervention_window_us, models):
        scheduler.stopped.wait()

    @contextmanager
    def open_client(*, now, subject_speaker_id):
        monkeypatch.setattr("normative_conformance.lifespan.run_worker", idle_worker)
        application = create_app(
            settings=Settings(
                app_db_path=tmp_path / "api.sqlite3",
                assessment_queue_path=tmp_path / "queue",
                log_dir=tmp_path / "logs",
                subject_speaker_id=subject_speaker_id,
            ),
            now=now,
        )
        with TestClient(application) as client:
            yield client

    return open_client
