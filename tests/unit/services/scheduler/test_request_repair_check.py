import sqlite3
from unittest.mock import Mock
from uuid import UUID

import pytest
from persistqueue import SQLiteAckQueue

from normative_conformance.errors import EnqueueFailed
from normative_conformance.services.scheduler.request_repair_check import request_repair_check
from normative_conformance.services.scheduler.state import SchedulerState


def test_requests_coalesce_only_while_the_case_is_waiting():
    queue = Mock(spec=SQLiteAckQueue)
    queue.queue.return_value = []
    scheduler = SchedulerState(queue=queue)
    request_repair_check(case_id="case", scheduler=scheduler)
    request_repair_check(case_id="case", scheduler=scheduler)
    assert scheduler.queued_repairs == {"case"}
    queue.put.assert_called_once()
    first = queue.put.call_args.kwargs["item"]
    assert first["kind"] == "check_repairs"
    assert first["case_id"] == "case"
    assert UUID(first["evaluation_id"]).version == 4
    scheduler.queued_repairs.remove("case")
    request_repair_check(case_id="case", scheduler=scheduler)
    assert queue.put.call_count == 2
    assert queue.put.call_args.kwargs["item"]["evaluation_id"] != first["evaluation_id"]


def test_stopped_worker_rejects_even_a_coalesced_request():
    queue = Mock(spec=SQLiteAckQueue)
    queue.queue.return_value = []
    scheduler = SchedulerState(queue=queue)
    scheduler.queued_repairs.add("case")
    scheduler.stopped.set()
    with pytest.raises(EnqueueFailed, match=r"^The assessment worker is not running$"):
        request_repair_check(case_id="case", scheduler=scheduler)
    queue.put.assert_not_called()


@pytest.mark.parametrize(
    "failure", [sqlite3.OperationalError("Queue failed"), OSError("Queue failed")]
)
def test_enqueue_failure_does_not_claim_the_case(*, failure):
    queue = Mock(spec=SQLiteAckQueue)
    queue.queue.return_value = []
    queue.put.side_effect = failure
    scheduler = SchedulerState(queue=queue)
    with pytest.raises(EnqueueFailed, match=r"^The repair check could not be queued$") as caught:
        request_repair_check(case_id="case", scheduler=scheduler)
    assert caught.value.__cause__ is failure
    assert scheduler.queued_repairs == set()
