import sqlite3
from uuid import uuid4

from normative_conformance.errors import EnqueueFailed
from normative_conformance.services.scheduler.state import SchedulerState


def request_assessment(
    *,
    case_id: str,
    scheduler: SchedulerState,
) -> None:
    """Keep at most one waiting assessment request per case."""
    with scheduler.lock:
        if scheduler.stopped.is_set():
            raise EnqueueFailed(message="The assessment worker is not running")
        if case_id in scheduler.queued_cases:
            return

        task = {
            "kind": "assess_case",
            "case_id": case_id,
            "evaluation_id": str(uuid4()),
        }

        try:
            scheduler.queue.put(item=task)
        except (sqlite3.Error, OSError) as error:
            raise EnqueueFailed(message="The assessment request could not be queued") from error

        scheduler.queued_cases.add(case_id)
