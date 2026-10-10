import sqlite3
from unittest.mock import Mock

import pytest

from normative_conformance.errors import EnqueueFailed
from normative_conformance.services.scheduler.request_repair_check import request_repair_check
from normative_conformance.services.scheduler.run_worker.enqueue_due_repair_checks import (
    enqueue_due_repair_checks,
)
from normative_conformance.services.scheduler.state import SchedulerState
from normative_conformance.timestamps import from_microseconds


def test_enqueues_due_cases_and_keeps_future_deadlines(*, assessment_queue):
    scheduler = SchedulerState(queue=assessment_queue)

    repair_deadlines = {"overdue": 99, "due": 100, "future": 101}

    enqueue_due_repair_checks(
        repair_deadlines=repair_deadlines,
        scheduler=scheduler,
        now=lambda: from_microseconds(value=100),
    )

    assert repair_deadlines == {"future": 101}
    assert scheduler.queued_repairs == {"overdue", "due"}
    assert [item["data"]["case_id"] for item in assessment_queue.queue()] == ["overdue", "due"]


def test_existing_request_consumes_deadline_without_another_task(*, assessment_queue):
    scheduler = SchedulerState(queue=assessment_queue)

    request_repair_check(case_id="case", scheduler=scheduler)
    repair_deadlines = {"case": 100}

    enqueue_due_repair_checks(
        repair_deadlines=repair_deadlines,
        scheduler=scheduler,
        now=lambda: from_microseconds(value=100),
    )

    assert repair_deadlines == {}
    assert assessment_queue.qsize() == 1


def test_enqueue_failure_preserves_deadline_and_escapes(*, assessment_queue, monkeypatch):
    scheduler = SchedulerState(queue=assessment_queue)

    repair_deadlines = {"case": 100}
    monkeypatch.setattr(
        assessment_queue, "put", Mock(side_effect=sqlite3.OperationalError("Queue failed"))
    )

    with pytest.raises(EnqueueFailed, match="The repair check could not be queued"):
        enqueue_due_repair_checks(
            repair_deadlines=repair_deadlines,
            scheduler=scheduler,
            now=lambda: from_microseconds(value=100),
        )

    assert repair_deadlines == {"case": 100}
    assert scheduler.queued_repairs == set()
    assert assessment_queue.qsize() == 0
