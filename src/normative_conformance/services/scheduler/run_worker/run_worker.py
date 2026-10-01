import logging

from sqlalchemy import Engine

from normative_conformance.schemas.internal import Clock
from normative_conformance.services.assessment.load_repair_deadlines import load_repair_deadlines
from normative_conformance.services.scheduler.run_worker.create_due_interventions import (
    create_due_interventions,
)
from normative_conformance.services.scheduler.run_worker.enqueue_due_repair_checks import (
    enqueue_due_repair_checks,
)
from normative_conformance.services.scheduler.run_worker.process_next_task import process_next_task
from normative_conformance.services.scheduler.state import SchedulerState

logger = logging.getLogger(__name__)


def run_worker(
    *,
    scheduler: SchedulerState,
    engine: Engine,
    now: Clock,
    intervention_window_us: int,
) -> None:
    intervention_windows: dict[str, int] = {}
    try:
        repair_deadlines = load_repair_deadlines(engine=engine)
        if repair_deadlines:
            logger.info(
                "Repair deadlines recovered",
                extra={"event": "worker.deadlines_recovered", "repair_deadlines": repair_deadlines},
            )

        while not scheduler.stopped.is_set():
            enqueue_due_repair_checks(
                repair_deadlines=repair_deadlines,
                scheduler=scheduler,
                now=now,
            )
            create_due_interventions(
                intervention_windows=intervention_windows,
                intervention_window_us=intervention_window_us,
                engine=engine,
                now=now,
            )
            process_next_task(
                scheduler=scheduler,
                engine=engine,
                now=now,
                repair_deadlines=repair_deadlines,
                intervention_windows=intervention_windows,
            )
    except Exception:
        logger.exception(
            "The assessment worker stopped unexpectedly",
            extra={
                "event": "worker.stopped",
                "discarded_intervention_windows": intervention_windows,
            },
        )
    finally:
        scheduler.stopped.set()
