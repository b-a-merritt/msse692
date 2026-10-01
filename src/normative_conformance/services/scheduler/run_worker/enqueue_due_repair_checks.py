from normative_conformance.schemas.internal import Clock
from normative_conformance.services.scheduler.request_repair_check import request_repair_check
from normative_conformance.services.scheduler.state import SchedulerState
from normative_conformance.timestamps import to_microseconds


def enqueue_due_repair_checks(
    *,
    repair_deadlines: dict[str, int],
    scheduler: SchedulerState,
    now: Clock,
) -> None:
    current_time_us = to_microseconds(value=now())
    for case_id, due_at_us in list(repair_deadlines.items()):
        if due_at_us <= current_time_us:
            request_repair_check(case_id=case_id, scheduler=scheduler)
            del repair_deadlines[case_id]
