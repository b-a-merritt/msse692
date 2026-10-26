from unittest.mock import Mock

from normative_conformance.routes import health
from normative_conformance.schemas.health import Readiness


def test_liveness_requires_no_dependencies():
    assert health.liveness().status == "live"


def test_readiness_passes_runtime_dependencies_to_service(*, monkeypatch):
    session, stopped, worker = object(), object(), object()
    result = Readiness(status="ready")
    operation = Mock(return_value=result)
    monkeypatch.setattr(health, "readiness", operation)
    assert health.check_readiness(session=session, stopped=stopped, worker=worker) is result
    operation.assert_called_once_with(session=session, stopped=stopped, worker=worker)
