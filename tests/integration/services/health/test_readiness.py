from contextlib import contextmanager
from threading import Event
from threading import Thread
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import OperationalError
from sqlmodel import select

from normative_conformance.errors import NotReady
from normative_conformance.models.observation import Observation
from normative_conformance.services.health.readiness import readiness


def test_ready_checks_leave_records_unchanged(*, session):
    stopped = Event()

    with _running_worker(stopped=stopped) as worker:
        result = readiness(session=session, stopped=stopped, worker=worker)

        assert result.model_dump() == {"status": "ready"}
        assert session.exec(select(Observation)).all() == []


def test_dead_worker_is_not_ready(*, session):
    stopped = Event()

    with pytest.raises(NotReady, match="The assessment worker is not running"):
        readiness(session=session, stopped=stopped, worker=Thread())


def test_stopping_worker_is_not_ready_even_while_thread_is_alive(*, session):
    stopped = Event()

    stopped.set()
    worker = Mock(spec=Thread)
    worker.is_alive.return_value = True
    with pytest.raises(NotReady, match="The assessment worker is not running"):
        readiness(session=session, stopped=stopped, worker=worker)


def test_database_failure_has_fixed_message_and_preserves_cause(*, session, engine, monkeypatch):
    stopped = Event()

    with _running_worker(stopped=stopped) as worker:
        error = OperationalError("connect", {}, RuntimeError("private database details"))
        monkeypatch.setattr(engine, "connect", Mock(side_effect=error))

        with pytest.raises(NotReady) as caught:
            readiness(session=session, stopped=stopped, worker=worker)

        assert str(caught.value) == "The application database is unavailable"
        assert caught.value.__cause__ is error


@contextmanager
def _running_worker(*, stopped):
    worker = Thread(target=stopped.wait, name="health-test-worker")
    worker.start()
    try:
        yield worker
    finally:
        stopped.set()
        worker.join(timeout=5)
        assert not worker.is_alive()
