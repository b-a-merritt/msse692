from contextlib import nullcontext
from importlib import import_module
from unittest.mock import Mock

from sqlmodel import Session

module = import_module("normative_conformance.services.scheduler.run_worker.pending_cases")


def test_returns_cases_from_storage_without_mutating_them(monkeypatch):
    session = Mock(spec=Session)
    session.exec.return_value.all.return_value = ["first", "second"]
    monkeypatch.setattr(module, "read_session", Mock(return_value=nullcontext(session)))
    assert module.pending_cases(engine=object(), now_us=100) == ["first", "second"]
    session.add.assert_not_called()
    session.commit.assert_not_called()
