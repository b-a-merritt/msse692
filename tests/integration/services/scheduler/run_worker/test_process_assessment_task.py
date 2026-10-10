from datetime import datetime
from datetime import timezone
from uuid import UUID

import pytest

from normative_conformance import models as db_models
from normative_conformance.database import read_session
from normative_conformance.services import assessment
from normative_conformance.services.model.list_models import list_models
from normative_conformance.services.scheduler.request_assessment import request_assessment
from normative_conformance.services.scheduler.request_repair_check import request_repair_check
from normative_conformance.services.scheduler.run_worker.process_assessment_task import (
    process_assessment_task,
)
from normative_conformance.services.scheduler.state import SchedulerState
from normative_conformance.timestamps import from_microseconds


@pytest.mark.parametrize("task_kind", ["assess_case", "check_repairs"])
@pytest.mark.parametrize("opened_at_us", [None, 90_000_000])
def test_releases_waiting_case_before_evaluation_and_preserves_follow_up(
    *, assessment_queue, engine, monkeypatch, task_kind, opened_at_us
):
    scheduler = SchedulerState(queue=assessment_queue)
    with read_session(engine=engine) as catalog_session:
        model_catalog = list_models(session=catalog_session)

    if task_kind == "assess_case":
        request = request_assessment
        request_other = request_repair_check
        waiting_case_ids = scheduler.queued_cases
        operation = "evaluate_case"
    else:
        request = request_repair_check
        request_other = request_assessment
        waiting_case_ids = scheduler.queued_repairs
        operation = "check_repairs"
    request(case_id="case", scheduler=scheduler)
    request_other(case_id="case", scheduler=scheduler)
    task = assessment_queue.get(block=False)
    repair_deadlines = {"case": 105_000_000, "other": 200_000_000}
    intervention_windows = {"other": 80_000_000}
    if opened_at_us is not None:
        intervention_windows["case"] = opened_at_us

    def clock():
        assert "case" not in waiting_case_ids
        return from_microseconds(value=100_000_000)

    def evaluate(*, case_id, evaluation_id, engine, now, scheduler, models):
        assert case_id == "case"
        assert evaluation_id == UUID(task["evaluation_id"])
        assert scheduler.lock.acquire(blocking=False)
        scheduler.lock.release()
        request(case_id=case_id, scheduler=scheduler)
        return [
            db_models.Assessment(
                case_id="case",
                evaluation_id="evaluation",
                model_id="harm_phrase",
                model_version="1",
                through_sequence=1,
                status="pending",
                evaluated_at_us=100_000_000,
                next_due_at_us=110_000_000,
                resolves_assessment_id=None,
                explanation_json="{}",
            ),
            db_models.Assessment(
                case_id="case",
                evaluation_id=str(evaluation_id),
                model_id="harm_phrase",
                model_version="1",
                through_sequence=1,
                status="conformant",
                evaluated_at_us=100_000_000,
                next_due_at_us=None,
                resolves_assessment_id=1 if task_kind == "check_repairs" else None,
                explanation_json="{}",
            ),
        ]

    monkeypatch.setattr(assessment, operation, evaluate)
    process_assessment_task(
        task=task,
        scheduler=scheduler,
        engine=engine,
        now=clock,
        repair_deadlines=repair_deadlines,
        intervention_windows=intervention_windows,
        models=model_catalog,
    )

    assert scheduler.queued_cases == {"case"}
    assert scheduler.queued_repairs == {"case"}
    assert assessment_queue.qsize() == 2
    assert assessment_queue.unack_count() == 1
    assert repair_deadlines == {"case": 110_000_000, "other": 200_000_000}
    assert intervention_windows == {
        "case": 100_000_000 if opened_at_us is None else opened_at_us,
        "other": 80_000_000,
    }


def test_no_results_clear_only_the_cases_repair_deadline(*, assessment_queue, engine, monkeypatch):
    scheduler = SchedulerState(queue=assessment_queue)
    received_at = datetime(2026, 9, 26, 9, 2, 3, 456_789, tzinfo=timezone.utc)
    with read_session(engine=engine) as catalog_session:
        model_catalog = list_models(session=catalog_session)

    request_assessment(case_id="case", scheduler=scheduler)
    task = assessment_queue.get(block=False)
    repair_deadlines = {"case": 100, "other": 200}
    intervention_windows = {"case": 50, "other": 60}
    monkeypatch.setattr(assessment, "evaluate_case", lambda **kwargs: [])

    process_assessment_task(
        task=task,
        scheduler=scheduler,
        engine=engine,
        now=lambda: received_at,
        repair_deadlines=repair_deadlines,
        intervention_windows=intervention_windows,
        models=model_catalog,
    )

    assert repair_deadlines == {"other": 200}
    assert intervention_windows == {"case": 50, "other": 60}
