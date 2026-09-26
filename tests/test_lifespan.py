"""Startup and shutdown own the persistent assessment queue."""

import pytest
from fastapi.testclient import TestClient

from normative_conformance.config import Settings
from normative_conformance.errors import EnqueueFailed
from normative_conformance.errors import StorageUnavailable
from normative_conformance.main import create_app
from normative_conformance.services.scheduler.request_assessment import request_assessment


def test_lifespan_initializes_and_closes_queue(*, tmp_path):
    application = create_app(
        settings=Settings(
            app_db_path=tmp_path / "app.sqlite3",
            assessment_queue_path=tmp_path / "queue",
        )
    )
    with TestClient(application):
        queue = application.state.assessment_queue
        assert application.state.engine is not None
        request_assessment(case_id="case", queue=queue)
        assert queue.qsize() == 1

    assert application.state.engine is None
    assert application.state.assessment_queue is None
    with pytest.raises(EnqueueFailed):
        request_assessment(case_id="case", queue=queue)


def test_failed_queue_startup_clears_application_resources(*, tmp_path):
    path = tmp_path / "file"
    path.write_text("not a directory", encoding="utf-8")
    application = create_app(
        settings=Settings(app_db_path=tmp_path / "app.sqlite3", assessment_queue_path=path)
    )

    with pytest.raises(StorageUnavailable), TestClient(application):
        pytest.fail("Startup should fail when the queue cannot be opened")

    assert application.state.engine is None
    assert application.state.assessment_queue is None
