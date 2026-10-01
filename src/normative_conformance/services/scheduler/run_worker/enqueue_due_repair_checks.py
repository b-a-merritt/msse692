import logging

from normative_conformance.schemas.internal import Clock
from normative_conformance.services.scheduler.request_repair_check import request_repair_check
from normative_conformance.services.scheduler.state import SchedulerState
from normative_conformance.timestamps import to_microseconds

logger = logging.getLogger(__name__)


def enqueue_due_repair_checks(
    *,
    repair_deadlines: dict[str, int],
    scheduler: SchedulerState,
    now: Clock,
) -> None:
    current_time_us = to_microseconds(value=now())
    for case_id, due_at_us in list(repair_deadlines.items()):
        if due_at_us <= current_time_us:
            logger.info(
                "Repair deadline due",
                extra={"event": "repairs.deadline_due", "case_id": case_id, "due_at_us": due_at_us},
            )
            request_repair_check(case_id=case_id, scheduler=scheduler)
            del repair_deadlines[case_id]
