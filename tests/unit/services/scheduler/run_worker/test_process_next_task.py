import sqlite3
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from persistqueue import SQLiteAckQueue
from persistqueue.exceptions import Empty

module = import_module("normative_conformance.services.scheduler.run_worker.process_next_task")


@pytest.mark.parametrize("failed", [False, True])
def test_acknowledges_only_after_processing_and_marks_failures_separately(*, monkeypatch, failed):
    task = {"kind": "assess_case", "case_id": "case", "evaluation_id": "evaluation"}
    queue = Mock(spec=SQLiteAckQueue)
    queue.get.return_value = task
    scheduler = SimpleNamespace(queue=queue)
    engine = object()
    clock = Mock()
    deadlines = {"case": 1}
    windows = {}

    def process(**kwargs):
        queue.ack.assert_not_called()
        queue.ack_failed.assert_not_called()
        assert kwargs["repair_deadlines"] is deadlines
        assert kwargs["intervention_windows"] is windows
        if failed:
            raise ValueError("Evaluation failed")

    process_mock = Mock(side_effect=process)
    monkeypatch.setattr(module, "process_assessment_task", process_mock)
    module.process_next_task(
        scheduler=scheduler,
        engine=engine,
        now=clock,
        repair_deadlines=deadlines,
        intervention_windows=windows,
        models=[],
    )
    queue.get.assert_called_once_with(timeout=0.1)
    process_mock.assert_called_once_with(
        task=task,
        scheduler=scheduler,
        engine=engine,
        now=clock,
        repair_deadlines=deadlines,
        intervention_windows=windows,
        models=[],
    )
    if failed:
        queue.ack_failed.assert_called_once_with(item=task)
        queue.ack.assert_not_called()
    else:
        queue.ack.assert_called_once_with(item=task)
        queue.ack_failed.assert_not_called()


def test_empty_poll_does_not_process_or_acknowledge(*, monkeypatch):
    queue = Mock(spec=SQLiteAckQueue)
    queue.get.side_effect = Empty()
    process = Mock()
    monkeypatch.setattr(module, "process_assessment_task", process)
    module.process_next_task(
        scheduler=SimpleNamespace(queue=queue),
        engine=object(),
        now=Mock(),
        repair_deadlines={},
        intervention_windows={},
        models=[],
    )
    process.assert_not_called()
    queue.ack.assert_not_called()
    queue.ack_failed.assert_not_called()


@pytest.mark.parametrize("operation", ["get", "ack", "ack_failed"])
def test_queue_failures_escape_so_the_worker_can_stop(*, monkeypatch, operation):
    queue = Mock(spec=SQLiteAckQueue)
    queue.get.return_value = {
        "kind": "assess_case",
        "case_id": "case",
        "evaluation_id": "evaluation",
    }
    failure = sqlite3.OperationalError("Queue failed")
    getattr(queue, operation).side_effect = failure
    monkeypatch.setattr(
        module,
        "process_assessment_task",
        Mock(side_effect=ValueError("Evaluation failed") if operation == "ack_failed" else None),
    )
    with pytest.raises(sqlite3.OperationalError) as caught:
        module.process_next_task(
            scheduler=SimpleNamespace(queue=queue),
            engine=object(),
            now=Mock(),
            repair_deadlines={},
            intervention_windows={},
            models=[],
        )
    assert caught.value is failure
