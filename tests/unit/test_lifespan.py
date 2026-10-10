import asyncio
from contextlib import nullcontext
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from persistqueue import SQLiteAckQueue
from sqlalchemy import Engine
from sqlmodel import Session

from normative_conformance.config import Settings
from normative_conformance.schemas.model import ModelVersion

module = import_module("normative_conformance.lifespan")


@pytest.mark.parametrize(
    "failure_stage", [None, "engine", "migration", "validation", "queue", "running"]
)
def test_resources_are_released_in_dependency_order_after_success_or_failure(
    *, monkeypatch, failure_stage
):
    settings = Settings(
        _env_file=None,
        app_db_path=Path("app.sqlite3"),
        assessment_queue_path=Path("queue"),
        log_dir=Path("logs"),
        subject_speaker_id="subject",
        intervention_window_us=10,
    )
    clock = Mock()
    app = SimpleNamespace(state=SimpleNamespace(settings=settings, clock=clock))
    engine = Mock(spec=Engine)
    session = Mock(spec=Session)
    queue = Mock(spec=SQLiteAckQueue)
    queue.queue.return_value = []
    worker = Mock()
    model = ModelVersion(
        model_id="harm_phrase",
        name="Threat",
        version="1",
        type="undesired",
        rules=[{"rule_id": "one", "description": "", "sql": "SELECT 1"}],
        parameters={},
    )
    order = []
    failure = RuntimeError("Lifecycle failed")
    creation = Mock(return_value=engine, side_effect=failure if failure_stage == "engine" else None)
    migration = Mock(side_effect=failure if failure_stage == "migration" else None)
    validation = Mock(
        return_value=[model], side_effect=failure if failure_stage == "validation" else None
    )
    open_queue = Mock(return_value=queue, side_effect=failure if failure_stage == "queue" else None)
    thread = Mock(return_value=worker)
    stop_logging = Mock(side_effect=lambda: order.append("logging"))
    for name, value in [
        ("create_database_engine", creation),
        ("initialize_database", migration),
        ("initialize_experiment_config", Mock()),
        ("read_session", Mock(side_effect=lambda **kwargs: nullcontext(session))),
        ("validate_models", validation),
        ("create_assessment_queue", open_queue),
        ("Thread", thread),
        ("start_logging", Mock(return_value=Path("logs/run.jsonl"))),
        ("stop_logging", stop_logging),
        ("get_subject_speaker_id", Mock(return_value="subject")),
        ("get_schema_revision", Mock(return_value="0002")),
    ]:
        monkeypatch.setattr(module, name, value)
    worker.start.side_effect = lambda: order.append("start")

    def join():
        assert app.state.scheduler.stopped.is_set()
        queue.close.assert_not_called()
        order.append("join")

    worker.join.side_effect = join
    queue.close.side_effect = lambda: order.append("queue")
    engine.dispose.side_effect = lambda: order.append("engine")

    async def run():
        async with module.lifespan(app):
            assert app.state.engine is engine
            assert app.state.assessment_queue is queue
            assert app.state.assessment_worker is worker
            assert thread.call_args.kwargs["kwargs"]["models"] == [model]
            assert thread.call_args.kwargs["kwargs"]["now"] is clock
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
        assert app.state.assessment_queue is None
        assert app.state.scheduler is None
        assert app.state.assessment_worker is None
        engine.dispose.assert_called_once()
        assert order == (
            ["start", "join", "queue", "engine", "logging"]
            if failure_stage in {None, "running"}
            else ["engine", "logging"]
        )
    stop_logging.assert_called_once()
