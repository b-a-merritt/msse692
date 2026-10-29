from contextlib import contextmanager
from datetime import UTC
from datetime import datetime
from importlib import import_module
from pathlib import Path
from unittest.mock import Mock

from normative_conformance.config import Settings
from normative_conformance.schemas.discovery import CaseTrace
from normative_conformance.schemas.discovery import DiscoveredModel

module = import_module("normative_conformance.commands.discover")


def _patch_storage(*, monkeypatch, traces):
    """Replace the database with test doubles that hand out one session."""
    engine = Mock()
    session = Mock()

    @contextmanager
    def open_session(*, engine):
        yield session

    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: Settings(_env_file=None, app_db_path=Path("prototype.sqlite3")),
    )
    monkeypatch.setattr(module, "create_database_engine", Mock(return_value=engine))
    monkeypatch.setattr(module, "initialize_database", Mock())
    monkeypatch.setattr(module, "read_session", open_session)
    monkeypatch.setattr(module, "write_session", open_session)
    monkeypatch.setattr(module, "load_traces", Mock(return_value=traces))
    return engine, session


def test_stores_a_model_from_the_traces_that_ended(*, monkeypatch, capsys):
    traces = [
        CaseTrace(events=["budgeting", "undesired_behavior"], assessment_ids=[1, 2]),
        CaseTrace(events=["budgeting", "chores"], assessment_ids=[3]),
        CaseTrace(events=["budgeting", "undesired_behavior"], assessment_ids=[4]),
        CaseTrace(events=["work", "budgeting", "undesired_behavior"], assessment_ids=[5]),
    ]
    engine, session = _patch_storage(monkeypatch=monkeypatch, traces=traces)
    model = DiscoveredModel(
        normative_model_id=1, discovered_at=datetime(2026, 1, 1, tzinfo=UTC), topics=["budgeting"]
    )
    store = Mock(return_value=model)
    monkeypatch.setattr(module, "store_model", store)

    module.discover()

    assert store.call_args.kwargs["topics"] == ["budgeting"]
    assert store.call_args.kwargs["assessment_ids"] == [1, 2, 4, 5]
    assert store.call_args.kwargs["session"] is session
    assert DiscoveredModel.model_validate_json(capsys.readouterr().out) == model
    engine.dispose.assert_called_once()


def test_too_few_ended_traces_store_nothing(*, monkeypatch, capsys):
    traces = [CaseTrace(events=["budgeting", "undesired_behavior"], assessment_ids=[1])]
    engine, _ = _patch_storage(monkeypatch=monkeypatch, traces=traces)
    store = Mock()
    monkeypatch.setattr(module, "store_model", store)

    module.discover()

    store.assert_not_called()
    assert capsys.readouterr().out == (
        "Fewer than 3 conversations ended in undesired behavior; no model was stored.\n"
    )
    engine.dispose.assert_called_once()
