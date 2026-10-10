from contextlib import nullcontext
from importlib import import_module
from unittest.mock import Mock

from sqlmodel import Session

from normative_conformance.models.assessment import Assessment

module = import_module("normative_conformance.services.assessment.load_repair_deadlines")


def test_loads_only_unresolved_pending_deadlines_and_selects_earliest_per_case(*, monkeypatch):
    session = Mock(spec=Session)
    engine = object()
    reading = Mock(return_value=nullcontext(session))
    listing = Mock(
        return_value=[
            Assessment(case_id=case, next_due_at_us=due)
            for case, due in [("a", 20), ("a", 10), ("b", 30)]
        ]
    )
    monkeypatch.setattr(module, "read_session", reading)
    monkeypatch.setattr(module, "list_assessments", listing)
    assert module.load_repair_deadlines(engine=engine) == {"a": 10, "b": 30}
    reading.assert_called_once_with(engine=engine)
    listing.assert_called_once_with(status="pending", unresolved=True, session=session)
