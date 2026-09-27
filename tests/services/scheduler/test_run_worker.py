"""The worker acknowledges results and preserves follow-up requests."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from datetime import timezone
from threading import Event
from threading import Thread
from unittest.mock import Mock
from uuid import uuid4

import pytest

from normative_conformance.errors import EnqueueFailed
from normative_conformance.services import assessment
from normative_conformance.services.scheduler.request_assessment import request_assessment
from normative_conformance.services.scheduler.request_repair_check import request_repair_check
from normative_conformance.services.scheduler.run_worker import run_worker


def test_success_is_acknowledged_after_evaluation(
    *, scheduler, assessment_queue, engine, received_at, monkeypatch
):
    request_assessment(case_id="case", scheduler=scheduler)
    queued = assessment_queue.queue()[0]["data"]

    def evaluate_case(*, case_id, evaluation_id, engine, now, scheduler):
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

    def evaluate_case(*, case_id, evaluation_id, engine, now, scheduler):
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

    def evaluate_case(*, case_id, evaluation_id, engine, now, scheduler):
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


def test_missing_case_is_marked_failed(
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


def test_unknown_task_is_failed_without_stopping_other_cases(
    *, scheduler, assessment_queue, engine, received_at, monkeypatch, caplog
):
    assessment_queue.put(
        item={"kind": "unknown", "case_id": "invalid", "evaluation_id": str(uuid4())}
    )
    request_assessment(case_id="next", scheduler=scheduler)
    evaluated = []

    def evaluate_case(*, case_id, evaluation_id, engine, now, scheduler):
        evaluated.append(case_id)
        scheduler.stopped.set()
        return []

    monkeypatch.setattr(assessment, "evaluate_case", evaluate_case)
    run_worker(scheduler=scheduler, engine=engine, now=lambda: received_at)

    assert evaluated == ["next"]
    assert assessment_queue.ack_failed_count() == 1
    assert assessment_queue.acked_count() == 1
    assert "Unknown assessment task kind" in caplog.text


@pytest.mark.parametrize("restart", [False, True])
def test_worker_checks_deadline_without_more_observations(
    *,
    engine,
    scheduler,
    assessment_queue,
    add_observation,
    monkeypatch,
    restart,
):
    add_observation(start=0, end=0.9, transcript="you are a liar", level=-17.0)
    deadline = Event()
    checked_early = Event()
    completed = Event()
    resolutions = []
    original_check = assessment.check_repairs

    def clock():
        return datetime.fromtimestamp(110 if deadline.is_set() else 100, timezone.utc)

    if restart:
        # Simulate an assessment finishing during shutdown, leaving only its stored deadline.
        scheduler.stopped.set()
        assessment.evaluate_case(
            case_id="case", evaluation_id=uuid4(), engine=engine, now=clock, scheduler=scheduler
        )
        scheduler.stopped.clear()
        assert assessment_queue.empty()
        deadline.set()
    else:
        request_assessment(case_id="case", scheduler=scheduler)

    def check_repairs(*, case_id, evaluation_id, engine, now, scheduler):
        results = original_check(
            case_id=case_id,
            evaluation_id=evaluation_id,
            engine=engine,
            now=now,
            scheduler=scheduler,
        )
        checked_early.set()
        resolutions.extend(row for row in results if row.resolves_assessment_id is not None)
        if resolutions:
            scheduler.stopped.set()
            completed.set()
        return results

    monkeypatch.setattr(assessment, "check_repairs", check_repairs)
    worker = Thread(
        target=run_worker, kwargs={"scheduler": scheduler, "engine": engine, "now": clock}
    )
    worker.start()
    try:
        if not restart:
            assert checked_early.wait(timeout=5)
            deadline.set()
        assert completed.wait(timeout=5)
    finally:
        scheduler.stopped.set()
        worker.join(timeout=5)
    assert not worker.is_alive()
    assert len(resolutions) == 1
    assert resolutions[0].status == "conformant"
    assert assessment_queue.acked_count() == (1 if restart else 3)


def test_repaired_match_requests_another_assessment(
    *, engine, scheduler, add_observation, monkeypatch
):
    add_observation(start=0, end=0.9, transcript="you are a liar", level=-17.0)

    def clock():
        return datetime.fromtimestamp(100, timezone.utc)

    assessment.evaluate_case(
        case_id="case", evaluation_id=uuid4(), engine=engine, now=clock, scheduler=scheduler
    )
    add_observation(start=1, end=2, transcript="I apologize", received=105)
    request_repair_check(case_id="case", scheduler=scheduler)
    assessed = []

    def evaluate_case(*, case_id, evaluation_id, engine, now, scheduler):
        assessed.append(case_id)
        scheduler.stopped.set()
        return []

    monkeypatch.setattr(assessment, "evaluate_case", evaluate_case)
    run_worker(
        scheduler=scheduler, engine=engine, now=lambda: datetime.fromtimestamp(105, timezone.utc)
    )
    assert assessed == ["case"]


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
