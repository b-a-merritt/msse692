"""Manage an HTTP client's resources; callers supply the clock."""

from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from normative_conformance.config import Settings
from normative_conformance.config import get_settings

# Default ASGI construction must not load a developer's local dotenv file.
with patch.dict(Settings.model_config, {"env_file": None}):
    from normative_conformance.main import create_app
get_settings.cache_clear()


@pytest.fixture
def open_client(*, tmp_path, monkeypatch):
    def idle_worker(*, stopped, engine, now, intervention_window_us, models):
        stopped.wait()

    @contextmanager
    def open_client(*, now):
        monkeypatch.setattr("normative_conformance.lifespan.run_worker", idle_worker)
        application = create_app(
            settings=Settings(
                _env_file=None,
                app_db_path=tmp_path / "api.sqlite3",
                log_dir=tmp_path / "logs",
            ),
            now=now,
        )
        with TestClient(application) as client:
            yield client

    return open_client
