import logging

from sqlalchemy import Engine

from normative_conformance.schemas.internal import Clock
from normative_conformance.schemas.model import ModelVersion
from normative_conformance.services.assessment.load_repair_deadlines import load_repair_deadlines
from normative_conformance.services.scheduler.run_worker.create_due_interventions import (
    create_due_interventions,
)
from normative_conformance.services.scheduler.run_worker.pending_cases import pending_cases
from normative_conformance.services.scheduler.run_worker.process_case import process_case
from normative_conformance.services.scheduler.state import SchedulerState
from normative_conformance.timestamps import to_microseconds

logger = logging.getLogger(__name__)


def run_worker(
    *,
    scheduler: SchedulerState,
    engine: Engine,
    now: Clock,
    intervention_window_us: int,
    models: list[ModelVersion],
) -> None:
    """Poll durable case progress and repair deadlines with a 0.1-second idle wait."""
    intervention_windows: dict[str, int] = {}
    try:
        while not scheduler.stopped.is_set():
            try:
                cases = pending_cases(engine=engine)
                current_time = to_microseconds(value=now())
                due = [
                    case_id
                    for case_id, deadline in load_repair_deadlines(engine=engine).items()
                    if deadline <= current_time
                ]
                # Each ready case gets one turn before any case is visited again.
                for case_id in dict.fromkeys([*due, *cases]):
                    if scheduler.stopped.is_set():
                        break
                    create_due_interventions(
                        intervention_windows=intervention_windows,
                        intervention_window_us=intervention_window_us,
                        engine=engine,
                        now=now,
                    )
                    try:
                        opened_at = process_case(
                            case_id=case_id, engine=engine, now=now, models=models
                        )
                        if opened_at is not None:
                            intervention_windows.setdefault(case_id, opened_at)
                    except Exception:
                        logger.exception(
                            "Case processing failed",
                            extra={
                                "event": "case.processing_failed",
                                "case_id": case_id,
                            },
                        )
                create_due_interventions(
                    intervention_windows=intervention_windows,
                    intervention_window_us=intervention_window_us,
                    engine=engine,
                    now=now,
                )
            except Exception:
                logger.exception("Database polling failed", extra={"event": "worker.poll_failed"})
            scheduler.stopped.wait(0.1)
    finally:
        scheduler.stopped.set()
