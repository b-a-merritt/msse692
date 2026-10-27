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


FAILURE = RuntimeError("Lifecycle failed")


@pytest.mark.parametrize(
    "startup_failures,running_failure,outcome,released",
    [
        pytest.param({}, None, nullcontext(), ["start", "join", "engine", "logging"], id="success"),
        pytest.param(
            {},
            FAILURE,
            pytest.raises(RuntimeError, match="Lifecycle failed"),
            ["start", "join", "engine", "logging"],
            id="running",
        ),
        pytest.param(
            {"create_database_engine": FAILURE},
            None,
            pytest.raises(RuntimeError, match="Lifecycle failed"),
            ["logging"],
            id="engine",
        ),
        pytest.param(
            {"initialize_database": FAILURE},
            None,
            pytest.raises(RuntimeError, match="Lifecycle failed"),
            ["engine", "logging"],
            id="migration",
        ),
        pytest.param(
            {"TypeSafeClient": FAILURE},
            None,
            pytest.raises(RuntimeError, match="Lifecycle failed"),
            ["engine", "logging"],
            id="client",
        ),
    ],
)
def test_resources_are_released_in_dependency_order_after_success_or_failure(
    *, monkeypatch, startup_failures, running_failure, outcome, released
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
    thread = Mock(return_value=worker)
    stop_logging = Mock(side_effect=lambda: order.append("logging"))
    doubles = {
        "create_database_engine": Mock(return_value=engine),
        "initialize_database": Mock(),
        "TypeSafeClient": Mock(return_value=nullcontext(client)),
        "Thread": thread,
        "start_logging": Mock(return_value=Path("logs/run.jsonl")),
        "stop_logging": stop_logging,
        "get_schema_revision": Mock(return_value="0001"),
    }
    for name, failure in startup_failures.items():
        doubles[name].side_effect = failure
    for name, value in doubles.items():
        monkeypatch.setattr(module, name, value)
    worker.start.side_effect = lambda: order.append("start")

    def join():
        assert app.state.worker_stopped.is_set()
        order.append("join")

    worker.join.side_effect = join
    engine.dispose.side_effect = lambda: order.append("engine")
    serve = Mock(side_effect=running_failure)

    async def run():
        async with module.lifespan(app):
            assert app.state.engine is engine
            assert app.state.assessment_worker is worker
            assert thread.call_args.kwargs["kwargs"]["client"] is client
            assert thread.call_args.kwargs["kwargs"]["now"] is clock
            assert thread.call_args.kwargs["kwargs"]["stopped"] is app.state.worker_stopped
            serve()

    with outcome:
        asyncio.run(run())

    assert order == released
    assert getattr(app.state, "engine", None) is None
    assert getattr(app.state, "worker_stopped", None) is None
    assert getattr(app.state, "assessment_worker", None) is None
    stop_logging.assert_called_once()
