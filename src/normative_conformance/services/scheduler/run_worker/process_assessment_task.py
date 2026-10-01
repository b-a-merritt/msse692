import logging
from _thread import LockType
from typing import Literal
from uuid import UUID

from sqlalchemy import Engine

from normative_conformance.models.assessment import Assessment
from normative_conformance.schemas.internal import Clock
from normative_conformance.services import assessment
from normative_conformance.services.assessment.find_earliest_repair_deadlines import (
    find_earliest_repair_deadlines,
)
from normative_conformance.services.intervention.should_open_intervention_window import (
    should_open_intervention_window,
)
from normative_conformance.services.scheduler.state import SchedulerState
from normative_conformance.timestamps import to_microseconds

logger = logging.getLogger(__name__)


def process_assessment_task(
    *,
    task: dict[str, str],
    scheduler: SchedulerState,
    engine: Engine,
    now: Clock,
    repair_deadlines: dict[str, int],
    intervention_windows: dict[str, int],
) -> None:
    if task["kind"] == "assess_case":
        task_kind: Literal["assess_case", "check_repairs"] = "assess_case"
        evaluate = assessment.evaluate_case
        waiting_case_ids = scheduler.queued_cases
    elif task["kind"] == "check_repairs":
        task_kind = "check_repairs"
        evaluate = assessment.check_repairs
        waiting_case_ids = scheduler.queued_repairs
    else:
        raise ValueError("Unknown assessment task kind")

    case_id = task["case_id"]

    # Allow follow-up requests before capturing the task's start time and history.
    _allow_follow_up_request(
        case_id=case_id,
        waiting_case_ids=waiting_case_ids,
        lock=scheduler.lock,
    )

    started_at_us = to_microseconds(value=now())
    assessments = evaluate(
        case_id=case_id,
        evaluation_id=UUID(task["evaluation_id"]),
        scheduler=scheduler,
        engine=engine,
        now=now,
    )

    _replace_case_repair_deadline(
        case_id=case_id,
        assessments=assessments,
        repair_deadlines=repair_deadlines,
    )

    if case_id not in intervention_windows and should_open_intervention_window(
        assessments=assessments,
        task_kind=task_kind,
        evaluation_id=task["evaluation_id"],
        started_at_us=started_at_us,
    ):
        intervention_windows[case_id] = started_at_us
        logger.info(
            "Intervention window opened",
            extra={
                "event": "intervention.window_opened",
                "case_id": case_id,
                "evaluation_id": task["evaluation_id"],
                "opened_at_us": started_at_us,
            },
        )


def _allow_follow_up_request(
    *,
    case_id: str,
    waiting_case_ids: set[str],
    lock: LockType,
) -> None:
    """Clear waiting membership before history capture so later arrivals can queue work."""
    with lock:
        waiting_case_ids.discard(case_id)


def _replace_case_repair_deadline(
    *,
    case_id: str,
    assessments: list[Assessment],
    repair_deadlines: dict[str, int],
) -> None:
    """Replace the case's deadline from its results, clearing it if none remains."""
    repair_deadlines.pop(case_id, None)
    repair_deadlines.update(find_earliest_repair_deadlines(assessments=assessments))
