import logging
from uuid import UUID

from persistqueue.exceptions import Empty
from sqlalchemy import Engine

from normative_conformance.database import read_session
from normative_conformance.models.assessment import Assessment
from normative_conformance.schemas.internal import Clock
from normative_conformance.services import assessment
from normative_conformance.services.scheduler.request_repair_check import request_repair_check
from normative_conformance.services.scheduler.state import SchedulerState
from normative_conformance.timestamps import to_microseconds

logger = logging.getLogger(__name__)


def run_worker(
    *,
    scheduler: SchedulerState,
    engine: Engine,
    now: Clock,
) -> None:
    """Process requests serially, finishing active work before shutdown."""
    try:
        with read_session(engine=engine) as session:
            pending = assessment.list_assessments(
                status="pending", unresolved=True, session=session
            )
            deadlines = _earliest_deadlines(rows=pending)
        while not scheduler.stopped.is_set():
            _enqueue_due_repairs(deadlines=deadlines, scheduler=scheduler, now=now)
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

                results = handle(
                    case_id=task["case_id"],
                    evaluation_id=UUID(task["evaluation_id"]),
                    scheduler=scheduler,
                    engine=engine,
                    now=now,
                )

                deadlines.pop(task["case_id"], None)
                deadlines.update(_earliest_deadlines(rows=results))
            except Exception:
                logger.exception("Case assessment failed")
                scheduler.queue.ack_failed(item=task)
            else:
                scheduler.queue.ack(item=task)
    except Exception:
        logger.exception("The assessment worker stopped unexpectedly")
    finally:
        scheduler.stopped.set()


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


def _earliest_deadlines(*, rows: list[Assessment]) -> dict[str, int]:
    """Map each case to the earliest repair deadline among its assessments."""
    deadlines: dict[str, int] = {}
    for row in rows:
        if row.next_due_at_us is not None:
            deadlines[row.case_id] = min(
                row.next_due_at_us, deadlines.get(row.case_id, row.next_due_at_us)
            )

    return deadlines
