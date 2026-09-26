import sqlite3
from threading import Thread
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import OperationalError
from sqlmodel import select

from normative_conformance.errors import NotReady
from normative_conformance.models.observation import Observation
from normative_conformance.services.health.readiness import readiness
from normative_conformance.services.scheduler.request_assessment import request_assessment


def test_ready_checks_leave_records_and_queue_unchanged(
    *, session, scheduler, worker, assessment_queue
):
    request_assessment(case_id="case", scheduler=scheduler)
    waiting = assessment_queue.queue()

    result = readiness(session=session, scheduler=scheduler, worker=worker)

    assert result.model_dump() == {"status": "ready"}
    assert assessment_queue.queue() == waiting
    assert scheduler.queued_cases == {"case"}
    assert session.exec(select(Observation)).all() == []


def test_dead_worker_is_not_ready(*, session, scheduler):
    with pytest.raises(NotReady, match="The assessment worker is not running"):
        readiness(session=session, scheduler=scheduler, worker=Thread())


def test_stopping_worker_is_not_ready_even_while_thread_is_alive(*, session, scheduler):
    scheduler.stopped.set()
    worker = Mock(spec=Thread)
    worker.is_alive.return_value = True
    with pytest.raises(NotReady, match="The assessment worker is not running"):
        readiness(session=session, scheduler=scheduler, worker=worker)


def test_database_failure_has_fixed_message_and_preserves_cause(
    *, session, engine, scheduler, worker, monkeypatch
):
    error = OperationalError("connect", {}, RuntimeError("private database details"))
    monkeypatch.setattr(engine, "connect", Mock(side_effect=error))

    with pytest.raises(NotReady) as caught:
        readiness(session=session, scheduler=scheduler, worker=worker)

    assert str(caught.value) == "The application database is unavailable"
    assert caught.value.__cause__ is error


def test_closed_queue_is_not_ready(*, session, scheduler, worker, assessment_queue):
    assessment_queue.close()

    with pytest.raises(NotReady) as caught:
        readiness(session=session, scheduler=scheduler, worker=worker)

    assert str(caught.value) == "The assessment queue is unavailable"
    assert isinstance(caught.value.__cause__, sqlite3.ProgrammingError)
