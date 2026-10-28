from datetime import UTC
from datetime import datetime
from importlib import import_module
from threading import Event
from unittest.mock import Mock

module = import_module("normative_conformance.services.scheduler.run_worker.run_worker")


def test_polls_each_ready_case_once_per_pass(monkeypatch):
    stopped = Event()
    polls = []
    client = object()

    def wait(seconds):
        assert seconds == 1
        polls.append(seconds)
        if len(polls) == 2:
            stopped.set()

    process = Mock()
    monkeypatch.setattr(stopped, "wait", wait)
    monkeypatch.setattr(module, "pending_cases", Mock(return_value=["due", "new"]))
    monkeypatch.setattr(module, "process_case", process)
    module.run_worker(
        stopped=stopped,
        engine=object(),
        now=lambda: datetime(1970, 1, 1, tzinfo=UTC),
        client=client,
        max_batch_seconds=45,
        idle_seconds=15,
        context_seconds=20,
    )
    assert [call.kwargs["case_id"] for call in process.call_args_list] == [
        "due",
        "new",
        "due",
        "new",
    ]
    assert process.call_args.kwargs["client"] is client
    assert process.call_args.kwargs["max_batch_seconds"] == 45
    assert process.call_args.kwargs["idle_seconds"] == 15
    assert process.call_args.kwargs["context_seconds"] == 20


def test_failed_poll_is_retried_after_the_wait(monkeypatch):
    stopped = Event()
    visited = []
    waits = []
    pending = Mock(side_effect=[RuntimeError("Unavailable"), ["good"]])

    def wait(seconds):
        waits.append(seconds)
        if len(waits) == 2:
            stopped.set()

    monkeypatch.setattr(stopped, "wait", wait)
    monkeypatch.setattr(module, "pending_cases", pending)
    monkeypatch.setattr(module, "process_case", lambda **kwargs: visited.append(kwargs["case_id"]))
    module.run_worker(
        stopped=stopped,
        engine=object(),
        now=lambda: datetime(1970, 1, 1, tzinfo=UTC),
        client=object(),
        max_batch_seconds=60,
        idle_seconds=20,
        context_seconds=30,
    )
    assert visited == ["good"]
    assert waits == [1, 1]


def test_failed_case_does_not_stop_the_others(monkeypatch):
    stopped = Event()
    visited = []

    def process(**kwargs):
        visited.append(kwargs["case_id"])
        if kwargs["case_id"] == "bad":
            raise RuntimeError("Failed evaluation")

    monkeypatch.setattr(stopped, "wait", lambda seconds: stopped.set())
    monkeypatch.setattr(module, "pending_cases", lambda **kwargs: ["bad", "good"])
    monkeypatch.setattr(module, "process_case", process)
    module.run_worker(
        stopped=stopped,
        engine=object(),
        now=lambda: datetime(1970, 1, 1, tzinfo=UTC),
        client=object(),
        max_batch_seconds=60,
        idle_seconds=20,
        context_seconds=30,
    )
    assert visited == ["bad", "good"]


def test_shutdown_finishes_current_case_without_starting_next(monkeypatch):
    stopped = Event()
    process = Mock(side_effect=lambda **kwargs: stopped.set())
    monkeypatch.setattr(module, "pending_cases", Mock(return_value=["one", "two"]))
    monkeypatch.setattr(module, "process_case", process)
    module.run_worker(
        stopped=stopped,
        engine=object(),
        now=lambda: datetime(1970, 1, 1, tzinfo=UTC),
        client=object(),
        max_batch_seconds=60,
        idle_seconds=20,
        context_seconds=30,
    )
    assert [call.kwargs["case_id"] for call in process.call_args_list] == ["one"]
