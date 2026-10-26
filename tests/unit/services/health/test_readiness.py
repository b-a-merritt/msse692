from threading import Thread
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from normative_conformance.errors import NotReady
from normative_conformance.services.health.readiness import readiness


@pytest.mark.parametrize("stopped,alive", [(True, True), (False, False)])
def test_worker_must_be_running_before_any_storage_probe(*, stopped, alive):
    session = Mock(spec=Session)
    stopped_event = Mock(is_set=Mock(return_value=stopped))
    worker = Mock(spec=Thread)
    worker.is_alive.return_value = alive
    with pytest.raises(NotReady, match=r"^The assessment worker is not running$"):
        readiness(session=session, stopped=stopped_event, worker=worker)
    session.exec.assert_not_called()


@pytest.mark.parametrize(
    "failure",
    [
        None,
        SQLAlchemyError("Database failed"),
    ],
)
def test_probes_storage_read_only_and_preserves_failure_causes(*, failure):
    session = Mock(spec=Session)
    worker = Mock(spec=Thread)
    worker.is_alive.return_value = True
    stopped = Mock(is_set=Mock(return_value=False))
    if isinstance(failure, SQLAlchemyError):
        session.exec.side_effect = failure
    if failure is None:
        assert readiness(session=session, stopped=stopped, worker=worker).status == "ready"
    else:
        with pytest.raises(NotReady) as caught:
            readiness(session=session, stopped=stopped, worker=worker)
        assert caught.value.__cause__ is failure
        assert str(caught.value) == "The application database is unavailable"
    session.commit.assert_not_called()
