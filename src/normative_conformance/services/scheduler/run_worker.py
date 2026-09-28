import logging
from typing import Literal
from uuid import UUID

from persistqueue.exceptions import Empty
from sqlalchemy import Engine

from normative_conformance.database import read_session
from normative_conformance.database import write_session
from normative_conformance.models.assessment import Assessment
from normative_conformance.schemas.internal import Clock
from normative_conformance.services import assessment
from normative_conformance.services import intervention
from normative_conformance.services.scheduler.request_repair_check import request_repair_check
from normative_conformance.services.scheduler.state import SchedulerState
from normative_conformance.timestamps import to_microseconds

logger = logging.getLogger(__name__)


def run_worker(
    *,
    scheduler: SchedulerState,
    engine: Engine,
    now: Clock,
    intervention_window_us: int,
) -> None:
    """Process requests serially, finishing active work before shutdown."""
    try:
        with read_session(engine=engine) as session:
            pending = assessment.list_assessments(
                status="pending", unresolved=True, session=session
            )
            deadlines = _earliest_deadlines(rows=pending)
        # Each case's open intervention window, keyed to the time it opened
        windows: dict[str, int] = {}
        while not scheduler.stopped.is_set():
            _enqueue_due_repairs(
                deadlines=deadlines,
                scheduler=scheduler,
                now=now,
            )
            _create_due_interventions(
                windows=windows,
                window_us=intervention_window_us,
                engine=engine,
                now=now,
            )

            try:
                task = scheduler.queue.get(timeout=0.1)
            except Empty:
                continue

            try:
                if task["kind"] == "assess_case":
                    handle = assessment.evaluate_case
                    queued = scheduler.queued_cases
                elif task["kind"] == "check_repairs":
                    handle = assessment.check_repairs
                    queued = scheduler.queued_repairs
                else:
                    raise ValueError("Unknown assessment task kind")

                with scheduler.lock:
                    # Clear before evaluation captures history so later arrivals can queue work
                    queued.discard(task["case_id"])

                started_at_us = to_microseconds(value=now())
                results = handle(
                    case_id=task["case_id"],
                    evaluation_id=UUID(task["evaluation_id"]),
                    scheduler=scheduler,
                    engine=engine,
                    now=now,
                )

                deadlines.pop(task["case_id"], None)
                deadlines.update(_earliest_deadlines(rows=results))

                # Only a new undesired confirmation opens a window; all eligible
                # confirmations accumulated before the decision can share it.
                if _has_new_confirmation(
                    rows=results,
                    task_kind=task["kind"],
                    evaluation_id=task["evaluation_id"],
                    started_at_us=started_at_us,
                ):
                    windows.setdefault(task["case_id"], started_at_us)
            except Exception:
                logger.exception("Case assessment failed")
                scheduler.queue.ack_failed(item=task)
            else:
                scheduler.queue.ack(item=task)
    except Exception:
        logger.exception("The assessment worker stopped unexpectedly")
    finally:
        scheduler.stopped.set()


def _has_new_confirmation(
    *,
    rows: list[Assessment],
    task_kind: Literal["assess_case", "check_repairs"],
    evaluation_id: str,
    started_at_us: int,
) -> bool:
    """Exclude reused results, replays, and successful repairs from window triggers."""
    # Case evaluation only returns undesired matches. In a repair check,
    # undesired confirmations resolve pending assessments; repairs themselves do not.
    return any(
        row.status == "conformant"
        and row.evaluation_id == evaluation_id
        and row.evaluated_at_us >= started_at_us
        and (task_kind == "assess_case" or row.resolves_assessment_id is not None)
        for row in rows
    )


def _enqueue_due_repairs(
    *,
    deadlines: dict[str, int],
    scheduler: SchedulerState,
    now: Clock,
) -> None:
    current_time = to_microseconds(value=now())
    for case_id, due_at in list(deadlines.items()):
        if due_at <= current_time:
            request_repair_check(case_id=case_id, scheduler=scheduler)
            del deadlines[case_id]


def _create_due_interventions(
    *,
    windows: dict[str, int],
    window_us: int,
    engine: Engine,
    now: Clock,
) -> None:
    """Decide each closed window once; a failure drops it without filling the gap later."""
    current_time = to_microseconds(value=now())
    for case_id, opened_at in list(windows.items()):
        if opened_at + window_us > current_time:
            continue

        del windows[case_id]
        try:
            with write_session(engine=engine) as session:
                intervention.create_intervention(
                    case_id=case_id, since_us=opened_at, session=session, now=now
                )
        except Exception:
            logger.exception("Intervention creation failed")


def _earliest_deadlines(*, rows: list[Assessment]) -> dict[str, int]:
    """Map each case to the earliest repair deadline among its assessments."""
    deadlines: dict[str, int] = {}
    for row in rows:
        if row.next_due_at_us is not None:
            deadlines[row.case_id] = min(
                row.next_due_at_us, deadlines.get(row.case_id, row.next_due_at_us)
            )

    return deadlines
