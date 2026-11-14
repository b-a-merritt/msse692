from contextlib import contextmanager
from threading import Event
from threading import Thread
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import OperationalError

from conversation_monitor.errors import NotReady
from conversation_monitor.services.health.readiness import readiness


def test_running_worker_and_database_are_ready(*, session):
    stopped = Event()

    with _running_worker(stopped=stopped) as worker:
        result = readiness(session=session, stopped=stopped, worker=worker)

        assert result.model_dump() == {"status": "ready"}


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
