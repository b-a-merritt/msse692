"""Requests for one waiting case share a single queued evaluation."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import pytest

from normative_conformance.errors import EnqueueFailed
from normative_conformance.services.scheduler.request_assessment import request_assessment
from normative_conformance.services.scheduler.state import SchedulerState


def test_reuses_waiting_case_request(*, assessment_queue):
    scheduler = SchedulerState(queue=assessment_queue)

    request_assessment(case_id="case", scheduler=scheduler)
    request_assessment(case_id="case", scheduler=scheduler)
    request_assessment(case_id="other", scheduler=scheduler)

    tasks = [assessment_queue.get(block=False) for _ in range(2)]
    assert assessment_queue.empty()
    assert {task["case_id"] for task in tasks} == {"case", "other"}
    assert len({task["evaluation_id"] for task in tasks}) == 2
    for task in tasks:
        assert set(task) == {"kind", "case_id", "evaluation_id"}
        assert task["kind"] == "assess_case"
        assert UUID(task["evaluation_id"]).version == 4


def test_queue_failure_has_fixed_message_and_preserves_cause(*, assessment_queue):
    scheduler = SchedulerState(queue=assessment_queue)

    assessment_queue.close()

    with pytest.raises(EnqueueFailed) as caught:
        request_assessment(case_id="case", scheduler=scheduler)

    assert str(caught.value) == "The assessment request could not be queued"
    assert isinstance(caught.value.__cause__, sqlite3.ProgrammingError)
    assert caught.value.committed_observation is None
    assert scheduler.queued_cases == set()


def test_concurrent_requests_for_same_case_enqueue_once(*, assessment_queue):
    scheduler = SchedulerState(queue=assessment_queue)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(request_assessment, case_id="case", scheduler=scheduler)
            for _ in range(8)
        ]
        for future in futures:
            future.result(timeout=10)

    assert assessment_queue.qsize() == 1
    assert assessment_queue.get(block=False)["case_id"] == "case"


def test_stopped_worker_rejects_request(*, assessment_queue):
    scheduler = SchedulerState(queue=assessment_queue)

    scheduler.stopped.set()
    with pytest.raises(EnqueueFailed, match="The assessment worker is not running"):
        request_assessment(case_id="case", scheduler=scheduler)
    assert assessment_queue.empty()
