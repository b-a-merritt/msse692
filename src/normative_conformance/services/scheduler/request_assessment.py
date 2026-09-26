import sqlite3
from uuid import uuid4

from persistqueue import SQLiteAckQueue

from normative_conformance.errors import EnqueueFailed


def request_assessment(
    *,
    case_id: str,
    queue: SQLiteAckQueue,
) -> None:
    """Persist a case assessment request without running the evaluation."""
    task = {"kind": "assess_case", "case_id": case_id, "evaluation_id": str(uuid4())}
    try:
        queue.put(item=task)
    except (sqlite3.Error, OSError) as error:
        raise EnqueueFailed(message="The assessment request could not be queued") from error
