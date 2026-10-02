import logging

from persistqueue.exceptions import Empty
from sqlalchemy import Engine

from normative_conformance.schemas.internal import Clock
from normative_conformance.schemas.model import ModelVersion
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
    models: list[ModelVersion],
) -> None:
    try:
        task = scheduler.queue.get(timeout=0.1)
    except Empty:
        return

    task_fields = {
        "task_kind": task.get("kind"),
        "case_id": task.get("case_id"),
        "evaluation_id": task.get("evaluation_id"),
    }
    logger.info("Task started", extra={"event": "task.started", **task_fields})

    try:
        process_assessment_task(
            task=task,
            scheduler=scheduler,
            engine=engine,
            now=now,
            repair_deadlines=repair_deadlines,
            intervention_windows=intervention_windows,
            models=models,
        )
    except Exception:
        logger.exception("Case assessment failed", extra={"event": "task.failed", **task_fields})
        scheduler.queue.ack_failed(item=task)
    else:
        scheduler.queue.ack(item=task)
