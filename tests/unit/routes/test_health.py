from unittest.mock import Mock

from normative_conformance.routes import health
from normative_conformance.schemas.health import Readiness


def test_liveness_requires_no_dependencies():
    assert health.liveness().status == "live"


def test_readiness_passes_runtime_dependencies_to_service(*, monkeypatch):
    session, scheduler, worker = object(), object(), object()
    result = Readiness(status="ready")
    operation = Mock(return_value=result)
    monkeypatch.setattr(health.health, "readiness", operation)
    assert health.readiness(session=session, scheduler=scheduler, worker=worker) is result
    operation.assert_called_once_with(session=session, scheduler=scheduler, worker=worker)
