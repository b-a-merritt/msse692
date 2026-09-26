"""Startup and shutdown own the queue and its worker thread."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Event
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from normative_conformance.config import Settings
from normative_conformance.errors import StorageUnavailable
from normative_conformance.main import create_app
from normative_conformance.models.observation import Observation
from normative_conformance.queue import create_assessment_queue
from normative_conformance.services import assessment
from normative_conformance.services.scheduler.request_assessment import request_assessment


def test_lifespan_runs_submitted_assessment_and_closes_resources(
    *, tmp_path, observation_data, received_at, monkeypatch
):
    handled = Event()
    calls = []

    def evaluate_case(*, case_id, evaluation_id, engine, now, scheduler):
        with Session(bind=engine) as session:
            assert session.get(Observation, (case_id, "chunk")) is not None
        calls.append((case_id, evaluation_id, now()))
        handled.set()
        return []

    monkeypatch.setattr(assessment, "evaluate_case", evaluate_case)
    application = create_app(
        settings=Settings(
            app_db_path=tmp_path / "app.sqlite3",
            assessment_queue_path=tmp_path / "queue",
        ),
        now=lambda: received_at,
    )
    with TestClient(application) as client:
        worker = application.state.assessment_worker
        queue = application.state.assessment_queue
        assert worker.is_alive()
        response = client.post("/api/v1/observations", json=observation_data)
        assert response.status_code == 202
        assert handled.wait(timeout=5)

    assert not worker.is_alive()
    assert calls[0][0] == "case"
    assert isinstance(calls[0][1], UUID)
    assert calls[0][2] == received_at
    assert application.state.engine is None
    assert application.state.assessment_queue is None
    assert application.state.scheduler is None
    assert application.state.assessment_worker is None
    with pytest.raises(sqlite3.ProgrammingError):
        queue.get(block=False)
    with closing(create_assessment_queue(path=tmp_path / "queue")) as reopened:
        assert reopened.acked_count() == 1
        assert reopened.empty()


def test_shutdown_finishes_active_work_and_leaves_waiting_work(*, tmp_path, monkeypatch):
    entered = Event()
    release = Event()
    evaluated = []

    def evaluate_case(*, case_id, evaluation_id, engine, now, scheduler):
        evaluated.append(case_id)
        entered.set()
        assert release.wait(timeout=5)
        # Shutdown must keep the queue open until the active evaluation finishes.
        assert application.state.assessment_queue.unack_count() == 1
        return []

    monkeypatch.setattr(assessment, "evaluate_case", evaluate_case)
    application = create_app(
        settings=Settings(
            app_db_path=tmp_path / "app.sqlite3",
            assessment_queue_path=tmp_path / "queue",
        )
    )
    with ThreadPoolExecutor(max_workers=1) as executor:
        with TestClient(application):
            scheduler = application.state.scheduler
            worker = application.state.assessment_worker
            request_assessment(case_id="active", scheduler=scheduler)
            assert entered.wait(timeout=5)
            request_assessment(case_id="waiting", scheduler=scheduler)

            def finish_during_shutdown():
                try:
                    assert scheduler.stopped.wait(timeout=5)
                    assert worker.is_alive()
                finally:
                    release.set()

            future = executor.submit(finish_during_shutdown)
        future.result(timeout=5)

    assert not worker.is_alive()
    assert evaluated == ["active"]
    with closing(create_assessment_queue(path=tmp_path / "queue")) as reopened:
        assert reopened.acked_count() == 1
        assert reopened.qsize() == 1
        assert reopened.get(block=False)["case_id"] == "waiting"


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
    assert application.state.scheduler is None
    assert application.state.assessment_worker is None
