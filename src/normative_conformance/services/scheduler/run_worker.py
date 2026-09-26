import logging
from uuid import UUID

from persistqueue.exceptions import Empty
from sqlalchemy import Engine

from normative_conformance.schemas.internal import Clock
from normative_conformance.services import assessment
from normative_conformance.services.scheduler.state import SchedulerState

logger = logging.getLogger(__name__)


def run_worker(
    *,
    scheduler: SchedulerState,
    engine: Engine,
    now: Clock,
) -> None:
    """Process requests serially, finishing active work before shutdown."""
    try:
        while not scheduler.stopped.is_set():
            try:
                task = scheduler.queue.get(timeout=0.1)
            except Empty:
                continue

            with scheduler.lock:
                # Clear before evaluation captures history so later arrivals can queue work
                scheduler.queued_cases.discard(task["case_id"])

            try:
                assessment.evaluate_case(
                    case_id=task["case_id"],
                    evaluation_id=UUID(task["evaluation_id"]),
                    engine=engine,
                    now=now,
                )
            except Exception:
                logger.exception("Case assessment failed")
                acknowledged = scheduler.queue.ack_failed(item=task)
            else:
                acknowledged = scheduler.queue.ack(item=task)

            if acknowledged is None:
                raise RuntimeError("The assessment request could not be acknowledged")
    except Exception:
        logger.exception("The assessment worker stopped unexpectedly")
    finally:
        scheduler.stopped.set()
