import sqlite3
from uuid import uuid4

from normative_conformance.errors import EnqueueFailed
from normative_conformance.services.scheduler.state import SchedulerState


def request_repair_check(*, case_id: str, scheduler: SchedulerState) -> None:
    with scheduler.lock:
        if scheduler.stopped.is_set():
            raise EnqueueFailed(message="The assessment worker is not running")
        if case_id in scheduler.queued_repairs:
            return
        try:
            scheduler.queue.put(
                item={
                    "kind": "check_repairs",
                    "case_id": case_id,
                    "evaluation_id": str(uuid4()),
                }
            )
        except (sqlite3.Error, OSError) as error:
            raise EnqueueFailed(message="The repair check could not be queued") from error
        scheduler.queued_repairs.add(case_id)
