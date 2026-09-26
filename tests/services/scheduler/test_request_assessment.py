"""Request case assessments through the persistent queue."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import pytest

from normative_conformance.errors import EnqueueFailed
from normative_conformance.services.scheduler.request_assessment import request_assessment


def test_enqueues_case_and_new_evaluation_id(*, assessment_queue):
    request_assessment(case_id="case", queue=assessment_queue)
    request_assessment(case_id="case", queue=assessment_queue)

    first = assessment_queue.get(block=False)
    second = assessment_queue.get(block=False)
    assert set(first) == set(second) == {"kind", "case_id", "evaluation_id"}
    assert first["kind"] == second["kind"] == "assess_case"
    assert first["case_id"] == second["case_id"] == "case"
    assert UUID(first["evaluation_id"]).version == 4
    assert UUID(second["evaluation_id"]).version == 4
    assert first["evaluation_id"] != second["evaluation_id"]


def test_queue_failure_has_fixed_message_and_preserves_cause(*, assessment_queue):
    assessment_queue.close()

    with pytest.raises(EnqueueFailed) as caught:
        request_assessment(case_id="case", queue=assessment_queue)

    assert str(caught.value) == "The assessment request could not be queued"
    assert isinstance(caught.value.__cause__, sqlite3.ProgrammingError)
    assert caught.value.committed_observation is None


def test_requests_can_be_enqueued_from_multiple_threads(*, assessment_queue):
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(request_assessment, case_id=str(index), queue=assessment_queue)
            for index in range(8)
        ]
        for future in futures:
            future.result(timeout=10)

    tasks = [assessment_queue.get(block=False) for _ in range(8)]
    assert {task["case_id"] for task in tasks} == {str(index) for index in range(8)}
    assert len({task["evaluation_id"] for task in tasks}) == 8
