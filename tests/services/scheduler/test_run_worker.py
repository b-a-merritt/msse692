"""The worker acknowledges results and preserves follow-up requests."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from threading import Thread
from unittest.mock import Mock

import pytest

from normative_conformance.errors import EnqueueFailed
from normative_conformance.services import assessment
from normative_conformance.services.scheduler.request_assessment import request_assessment
from normative_conformance.services.scheduler.run_worker import run_worker


def test_success_is_acknowledged_after_evaluation(
    *, scheduler, assessment_queue, engine, received_at, monkeypatch
):
    request_assessment(case_id="case", scheduler=scheduler)
    queued = assessment_queue.queue()[0]["data"]

    def evaluate_case(*, case_id, evaluation_id, engine, now):
        assert case_id == "case"
        assert str(evaluation_id) == queued["evaluation_id"]
        assert now() == received_at
        assert assessment_queue.acked_count() == 0
        assert assessment_queue.unack_count() == 1
        scheduler.stopped.set()
        return []

    monkeypatch.setattr(assessment, "evaluate_case", evaluate_case)
    run_worker(scheduler=scheduler, engine=engine, now=lambda: received_at)
    assert assessment_queue.acked_count() == 1
    assert assessment_queue.unack_count() == 0
    assert scheduler.queued_cases == set()


def test_arrivals_during_evaluation_share_one_follow_up(
    *, scheduler, assessment_queue, engine, received_at, monkeypatch
):
    entered = Event()
    release = Event()
    evaluations = []

    def evaluate_case(*, case_id, evaluation_id, engine, now):
        evaluations.append(evaluation_id)
        if len(evaluations) == 1:
            entered.set()
            assert release.wait(timeout=5)
        else:
            scheduler.stopped.set()
        return []

    monkeypatch.setattr(assessment, "evaluate_case", evaluate_case)
    request_assessment(case_id="case", scheduler=scheduler)
    worker = Thread(
        target=run_worker,
        kwargs={"scheduler": scheduler, "engine": engine, "now": lambda: received_at},
    )
    worker.start()
    try:
        assert entered.wait(timeout=5)
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(request_assessment, case_id="case", scheduler=scheduler)
                for _ in range(8)
            ]
            for future in futures:
                future.result(timeout=5)
        assert assessment_queue.qsize() == 1
        release.set()
        worker.join(timeout=5)
        assert not worker.is_alive()
    finally:
        scheduler.stopped.set()
        release.set()
        worker.join(timeout=5)
    assert len(set(evaluations)) == 2
    assert assessment_queue.acked_count() == 2
    assert assessment_queue.empty()


def test_failed_evaluation_does_not_retry_or_stop_other_cases(
    *, scheduler, assessment_queue, engine, received_at, monkeypatch, caplog
):
    request_assessment(case_id="failing", scheduler=scheduler)
    request_assessment(case_id="next", scheduler=scheduler)
    evaluated = []

    def evaluate_case(*, case_id, evaluation_id, engine, now):
        evaluated.append(case_id)
        if case_id == "failing":
            raise RuntimeError("Evaluation failed")
        scheduler.stopped.set()
        return []

    monkeypatch.setattr(assessment, "evaluate_case", evaluate_case)
    run_worker(scheduler=scheduler, engine=engine, now=lambda: received_at)
    assert evaluated == ["failing", "next"]
    assert assessment_queue.ack_failed_count() == 1
    assert assessment_queue.acked_count() == 1
    assert assessment_queue.empty()
    assert "Case assessment failed" in caplog.text


def test_unimplemented_evaluation_is_marked_failed(
    *, scheduler, assessment_queue, engine, received_at, monkeypatch
):
    request_assessment(case_id="case", scheduler=scheduler)
    original_ack_failed = assessment_queue.ack_failed

    def ack_failed(*, item):
        scheduler.stopped.set()
        return original_ack_failed(item=item)

    monkeypatch.setattr(assessment_queue, "ack_failed", ack_failed)
    run_worker(scheduler=scheduler, engine=engine, now=lambda: received_at)
    assert assessment_queue.acked_count() == 0
    assert assessment_queue.ack_failed_count() == 1


@pytest.mark.parametrize("operation", ["get", "ack", "ack_failed"])
def test_queue_failure_stops_worker_and_rejects_new_requests(
    *, scheduler, assessment_queue, engine, received_at, monkeypatch, caplog, operation
):
    request_assessment(case_id="case", scheduler=scheduler)
    request_assessment(case_id="waiting", scheduler=scheduler)
    monkeypatch.setattr(
        assessment,
        "evaluate_case",
        Mock(side_effect=RuntimeError("Evaluation failed"))
        if operation == "ack_failed"
        else Mock(return_value=[]),
    )
    monkeypatch.setattr(
        assessment_queue, operation, Mock(side_effect=sqlite3.OperationalError("Queue failed"))
    )
    run_worker(scheduler=scheduler, engine=engine, now=lambda: received_at)
    assert scheduler.stopped.is_set()
    assert assessment_queue.acked_count() == 0
    assert assessment_queue.ack_failed_count() == 0
    assert assessment_queue.qsize() == (2 if operation == "get" else 1)
    assert assessment_queue.unack_count() == (0 if operation == "get" else 1)
    assert "The assessment worker stopped unexpectedly" in caplog.text
    with pytest.raises(EnqueueFailed, match="The assessment worker is not running"):
        request_assessment(case_id="new", scheduler=scheduler)
