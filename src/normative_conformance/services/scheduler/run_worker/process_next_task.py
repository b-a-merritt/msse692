import logging

from persistqueue.exceptions import Empty
from sqlalchemy import Engine

from normative_conformance.schemas.internal import Clock
from normative_conformance.services.scheduler.run_worker.process_assessment_task import (
    process_assessment_task,
)
from normative_conformance.services.scheduler.state import SchedulerState

logger = logging.getLogger(__name__)


def process_next_task(
    *,
    scheduler: SchedulerState,
    engine: Engine,
    now: Clock,
    repair_deadlines: dict[str, int],
    intervention_windows: dict[str, int],
) -> None:
    try:
        task = scheduler.queue.get(timeout=0.1)
    except Empty:
        return

    try:
        process_assessment_task(
            task=task,
            scheduler=scheduler,
            engine=engine,
            now=now,
            repair_deadlines=repair_deadlines,
            intervention_windows=intervention_windows,
        )
    except Exception:
        logger.exception("Case assessment failed")
        scheduler.queue.ack_failed(item=task)
    else:
        scheduler.queue.ack(item=task)
