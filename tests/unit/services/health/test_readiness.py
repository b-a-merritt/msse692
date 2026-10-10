import sqlite3
from threading import Thread
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from persistqueue import SQLiteAckQueue
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from normative_conformance.errors import NotReady
from normative_conformance.services.health.readiness import readiness


@pytest.mark.parametrize("stopped,alive", [(True, True), (False, False)])
def test_worker_must_be_running_before_any_storage_probe(*, stopped, alive):
    session = Mock(spec=Session)
    queue = Mock(spec=SQLiteAckQueue)
    scheduler = SimpleNamespace(stopped=Mock(is_set=Mock(return_value=stopped)), queue=queue)
    worker = Mock(spec=Thread)
    worker.is_alive.return_value = alive
    with pytest.raises(NotReady, match=r"^The assessment worker is not running$"):
        readiness(session=session, scheduler=scheduler, worker=worker)
    session.exec.assert_not_called()
    queue.ready_count.assert_not_called()


@pytest.mark.parametrize(
    "failure",
    [
        None,
        SQLAlchemyError("Database failed"),
        sqlite3.OperationalError("Queue failed"),
        OSError("Queue failed"),
    ],
)
def test_probes_storage_read_only_and_preserves_failure_causes(*, failure):
    session = Mock(spec=Session)
    queue = Mock(spec=SQLiteAckQueue)
    worker = Mock(spec=Thread)
    worker.is_alive.return_value = True
    scheduler = SimpleNamespace(stopped=Mock(is_set=Mock(return_value=False)), queue=queue)
    if isinstance(failure, SQLAlchemyError):
        session.exec.side_effect = failure
    else:
        queue.ready_count.side_effect = failure
    if failure is None:
        assert readiness(session=session, scheduler=scheduler, worker=worker).status == "ready"
    else:
        with pytest.raises(NotReady) as caught:
            readiness(session=session, scheduler=scheduler, worker=worker)
        assert caught.value.__cause__ is failure
        assert str(caught.value) == (
            "The application database is unavailable"
            if isinstance(failure, SQLAlchemyError)
            else "The assessment queue is unavailable"
        )
    session.commit.assert_not_called()
    queue.put.assert_not_called()
