import sqlite3
from unittest.mock import Mock

import pytest

from normative_conformance.services import assessment
from normative_conformance.services.scheduler.request_assessment import request_assessment
from normative_conformance.services.scheduler.run_worker.process_next_task import process_next_task
from normative_conformance.timestamps import to_microseconds


def test_success_is_acknowledged_after_evaluation_and_timer_updates(
    *,
    scheduler,
    assessment_queue,
    engine,
    received_at,
    assessment_result,
    monkeypatch,
    model_catalog,
):
    request_assessment(case_id="case", scheduler=scheduler)
    queued = assessment_queue.queue()[0]["data"]
    repair_deadlines = {"case": 10}
    intervention_windows = {}

    def evaluate_case(*, case_id, evaluation_id, engine, now, scheduler, models):
        assert case_id == "case"
        assert str(evaluation_id) == queued["evaluation_id"]
        assert now() == received_at
        assert assessment_queue.acked_count() == 0
        assert assessment_queue.unack_count() == 1
        return [
            assessment_result(
                evaluation_id=str(evaluation_id),
                evaluated_at_us=to_microseconds(value=received_at),
            )
        ]

    original_ack = assessment_queue.ack

    def ack(*, item):
        assert repair_deadlines == {}
        assert intervention_windows == {"case": to_microseconds(value=received_at)}
        return original_ack(item=item)

    monkeypatch.setattr(assessment, "evaluate_case", evaluate_case)
    monkeypatch.setattr(assessment_queue, "ack", ack)
    process_next_task(
        scheduler=scheduler,
        engine=engine,
        now=lambda: received_at,
        repair_deadlines=repair_deadlines,
        intervention_windows=intervention_windows,
        models=model_catalog,
    )

    assert assessment_queue.acked_count() == 1
    assert assessment_queue.unack_count() == 0
    assert scheduler.queued_cases == set()


def test_missing_case_is_marked_failed(
    *, scheduler, assessment_queue, engine, received_at, model_catalog
):
    request_assessment(case_id="case", scheduler=scheduler)

    process_next_task(
        scheduler=scheduler,
        engine=engine,
        now=lambda: received_at,
        repair_deadlines={},
        intervention_windows={},
        models=model_catalog,
    )

    assert assessment_queue.acked_count() == 0
    assert assessment_queue.ack_failed_count() == 1
    assert not scheduler.stopped.is_set()


def test_empty_poll_preserves_timers_and_returns(*, scheduler, engine, model_catalog):
    repair_deadlines = {"case": 10}
    intervention_windows = {"case": 5}
    now = Mock()

    process_next_task(
        scheduler=scheduler,
        engine=engine,
        now=now,
        repair_deadlines=repair_deadlines,
        intervention_windows=intervention_windows,
        models=model_catalog,
    )

    assert repair_deadlines == {"case": 10}
    assert intervention_windows == {"case": 5}
    assert not scheduler.stopped.is_set()
    now.assert_not_called()


@pytest.mark.parametrize("operation", ["get", "ack", "ack_failed"])
def test_queue_failure_escapes_to_the_worker(
    *, scheduler, assessment_queue, engine, received_at, monkeypatch, operation, model_catalog
):
    request_assessment(case_id="case", scheduler=scheduler)
    monkeypatch.setattr(
        assessment,
        "evaluate_case",
        Mock(side_effect=RuntimeError("Evaluation failed"))
        if operation == "ack_failed"
        else Mock(return_value=[]),
    )
    failure = sqlite3.OperationalError("Queue failed")
    monkeypatch.setattr(assessment_queue, operation, Mock(side_effect=failure))

    with pytest.raises(sqlite3.OperationalError) as caught:
        process_next_task(
            scheduler=scheduler,
            engine=engine,
            now=lambda: received_at,
            repair_deadlines={},
            intervention_windows={},
            models=model_catalog,
        )

    assert caught.value is failure
    assert assessment_queue.ack_failed_count() == 0
    assert assessment_queue.acked_count() == 0
