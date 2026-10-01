import pytest
from fastapi.testclient import TestClient

from normative_conformance.config import Settings
from normative_conformance.main import create_app


@pytest.fixture
def client(*, tmp_path, received_at, monkeypatch):
    def idle_worker(*, scheduler, engine, now, intervention_window_us):
        scheduler.stopped.wait()

    monkeypatch.setattr("normative_conformance.lifespan.run_worker", idle_worker)
    application = create_app(
        settings=Settings(
            app_db_path=tmp_path / "api.sqlite3",
            assessment_queue_path=tmp_path / "queue",
            log_dir=tmp_path / "logs",
        ),
        now=lambda: received_at,
    )
    with TestClient(application) as client:
        yield client
