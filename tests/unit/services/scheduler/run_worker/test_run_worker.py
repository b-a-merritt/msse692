from datetime import datetime
from datetime import timezone
from importlib import import_module
from unittest.mock import Mock

import pytest

from normative_conformance.services.scheduler.state import SchedulerState

module = import_module("normative_conformance.services.scheduler.run_worker.run_worker")


def test_polls_each_ready_case_once_and_keeps_the_first_window(monkeypatch):
    scheduler = SchedulerState()
    polls = []
    visited = []
    windows = []

    def wait(seconds):
        assert seconds == 0.1
        polls.append(seconds)
        if len(polls) == 2:
            scheduler.stopped.set()

    def process(**kwargs):
        visited.append(kwargs["case_id"])
        return 10 if not polls else 20

    def interventions(**kwargs):
        windows.append(dict(kwargs["intervention_windows"]))

    monkeypatch.setattr(scheduler.stopped, "wait", wait)
    monkeypatch.setattr(module, "pending_cases", Mock(return_value=["new", "due"]))
    monkeypatch.setattr(
        module, "load_repair_deadlines", Mock(return_value={"due": 1, "later": 999})
    )
    monkeypatch.setattr(module, "process_case", process)
    monkeypatch.setattr(module, "create_due_interventions", interventions)
    module.run_worker(
        scheduler=scheduler,
        engine=object(),
        models=[],
        intervention_window_us=30,
        now=lambda: datetime(1970, 1, 1, microsecond=100, tzinfo=timezone.utc),
    )
    assert visited == ["due", "new", "due", "new"]
    assert windows[-1] == {"due": 10, "new": 10}


@pytest.mark.parametrize("failure", ["poll", "case", None])
def test_failure_does_not_lose_work_and_idle_ticks_service_timers(monkeypatch, failure):
    scheduler = SchedulerState()
    visited = []
    waits = []

    def pending(**kwargs):
        if failure == "poll" and not waits:
            raise RuntimeError("Unavailable")
        return ["bad", "good"] if failure else []

    def process(**kwargs):
        visited.append(kwargs["case_id"])
        if kwargs["case_id"] == "bad":
            raise RuntimeError("Failed evaluation")
        return None

    def wait(seconds):
        waits.append(seconds)
        if len(waits) == 2:
            scheduler.stopped.set()

    timers = Mock()
    monkeypatch.setattr(scheduler.stopped, "wait", wait)
    monkeypatch.setattr(module, "pending_cases", pending)
    monkeypatch.setattr(module, "load_repair_deadlines", Mock(return_value={}))
    monkeypatch.setattr(module, "process_case", process)
    monkeypatch.setattr(module, "create_due_interventions", timers)
    module.run_worker(
        scheduler=scheduler,
        engine=object(),
        models=[],
        intervention_window_us=30,
        now=lambda: datetime(1970, 1, 1, tzinfo=timezone.utc),
    )
    assert visited == (["bad", "good"] * (1 if failure == "poll" else 2) if failure else [])
    assert timers.called
    assert waits == [0.1, 0.1]


def test_shutdown_finishes_current_case_without_starting_next(monkeypatch):
    scheduler = SchedulerState()
    process = Mock(side_effect=lambda **kwargs: scheduler.stopped.set())
    monkeypatch.setattr(module, "pending_cases", Mock(return_value=["one", "two"]))
    monkeypatch.setattr(module, "load_repair_deadlines", Mock(return_value={}))
    monkeypatch.setattr(module, "process_case", process)
    monkeypatch.setattr(module, "create_due_interventions", Mock())
    module.run_worker(
        scheduler=scheduler,
        engine=object(),
        models=[],
        intervention_window_us=30,
        now=lambda: datetime(1970, 1, 1, tzinfo=timezone.utc),
    )
    assert [call.kwargs["case_id"] for call in process.call_args_list] == ["one"]
