import asyncio
from contextlib import nullcontext
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import Engine

from normative_conformance.config import Settings

module = import_module("normative_conformance.lifespan")


@pytest.mark.parametrize("failure_stage", [None, "engine", "migration", "client", "running"])
def test_resources_are_released_in_dependency_order_after_success_or_failure(
    *, monkeypatch, failure_stage
):
    settings = Settings(
        _env_file=None,
        app_db_path=Path("app.sqlite3"),
        log_dir=Path("logs"),
    )
    clock = Mock()
    app = SimpleNamespace(state=SimpleNamespace(settings=settings, clock=clock))
    engine = Mock(spec=Engine)
    worker = Mock()
    client = Mock()
    order = []
    failure = RuntimeError("Lifecycle failed")
    creation = Mock(return_value=engine, side_effect=failure if failure_stage == "engine" else None)
    migration = Mock(side_effect=failure if failure_stage == "migration" else None)
    constructor = Mock(
        return_value=nullcontext(client), side_effect=failure if failure_stage == "client" else None
    )
    thread = Mock(return_value=worker)
    stop_logging = Mock(side_effect=lambda: order.append("logging"))
    for name, value in [
        ("create_database_engine", creation),
        ("initialize_database", migration),
        ("TypeSafeClient", constructor),
        ("Thread", thread),
        ("start_logging", Mock(return_value=Path("logs/run.jsonl"))),
        ("stop_logging", stop_logging),
        ("get_schema_revision", Mock(return_value="0001")),
    ]:
        monkeypatch.setattr(module, name, value)
    worker.start.side_effect = lambda: order.append("start")

    def join():
        assert app.state.worker_stopped.is_set()
        order.append("join")

    worker.join.side_effect = join
    engine.dispose.side_effect = lambda: order.append("engine")

    async def run():
        async with module.lifespan(app):
            assert app.state.engine is engine
            assert app.state.assessment_worker is worker
            assert thread.call_args.kwargs["kwargs"]["client"] is client
            assert thread.call_args.kwargs["kwargs"]["now"] is clock
            assert thread.call_args.kwargs["kwargs"]["stopped"] is app.state.worker_stopped
            if failure_stage == "running":
                raise failure

    if failure_stage:
        with pytest.raises(RuntimeError) as caught:
            asyncio.run(run())
        assert caught.value is failure
    else:
        asyncio.run(run())

    if failure_stage == "engine":
        assert order == ["logging"]
        engine.dispose.assert_not_called()
    else:
        assert app.state.engine is None
        assert app.state.worker_stopped is None
        assert app.state.assessment_worker is None
        engine.dispose.assert_called_once()
        assert order == (
            ["start", "join", "engine", "logging"]
            if failure_stage in {None, "running"}
            else ["engine", "logging"]
        )
    stop_logging.assert_called_once()
