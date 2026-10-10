from importlib import import_module
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

module = import_module("normative_conformance.services.scheduler.run_worker.run_worker")


@pytest.mark.parametrize("recovered", [{}, {"case": 100}])
def test_recovers_deadlines_then_checks_timers_before_each_task(*, monkeypatch, recovered):
    scheduler = SimpleNamespace(stopped=Event())
    monkeypatch.setattr(module, "load_repair_deadlines", Mock(return_value=recovered))
    order = []
    repair = Mock(side_effect=lambda **kwargs: order.append("repairs"))
    intervention = Mock(side_effect=lambda **kwargs: order.append("interventions"))

    def process(**kwargs):
        order.append("task")
        assert kwargs["repair_deadlines"] is recovered
        assert kwargs["intervention_windows"] == {}
        scheduler.stopped.set()

    task = Mock(side_effect=process)
    for name, value in [
        ("enqueue_due_repair_checks", repair),
        ("create_due_interventions", intervention),
        ("process_next_task", task),
    ]:
        monkeypatch.setattr(module, name, value)
    module.run_worker(
        scheduler=scheduler, engine=object(), now=Mock(), intervention_window_us=10, models=[]
    )
    assert order == ["repairs", "interventions", "task"]
    assert scheduler.stopped.is_set()
    assert repair.call_args.kwargs["repair_deadlines"] is recovered
    assert intervention.call_args.kwargs["intervention_window_us"] == 10


@pytest.mark.parametrize(
    "failure_stage",
    [
        "load_repair_deadlines",
        "enqueue_due_repair_checks",
        "create_due_interventions",
        "process_next_task",
    ],
)
def test_any_unhandled_failure_stops_the_worker(*, monkeypatch, failure_stage):
    scheduler = SimpleNamespace(stopped=Event())
    calls = []
    for name in [
        "load_repair_deadlines",
        "enqueue_due_repair_checks",
        "create_due_interventions",
        "process_next_task",
    ]:
        operation = Mock(
            return_value={},
            side_effect=RuntimeError("Runtime failed") if name == failure_stage else None,
        )
        monkeypatch.setattr(module, name, operation)
        calls.append(operation)
    module.run_worker(
        scheduler=scheduler, engine=object(), now=Mock(), intervention_window_us=10, models=[]
    )
    assert scheduler.stopped.is_set()
    failed_index = [
        "load_repair_deadlines",
        "enqueue_due_repair_checks",
        "create_due_interventions",
        "process_next_task",
    ].index(failure_stage)
    assert [call.call_count for call in calls] == [
        1 if index <= failed_index else 0 for index in range(4)
    ]
