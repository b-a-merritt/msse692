from unittest.mock import Mock

from persistqueue import SQLiteAckQueue
from persistqueue.sqlackqueue import AckStatus

from normative_conformance.services.scheduler.state import SchedulerState


def test_restores_only_waiting_requests_and_keeps_task_kinds_separate():
    queue = Mock(spec=SQLiteAckQueue)
    queue.queue.return_value = [
        {"status": int(status), "data": {"kind": kind, "case_id": case}}
        for status, kind, case in [
            (AckStatus.inited, "assess_case", "assessment"),
            (AckStatus.ready, "check_repairs", "repair"),
            (AckStatus.acked, "assess_case", "finished"),
            (AckStatus.ack_failed, "check_repairs", "failed"),
            (AckStatus.unack, "assess_case", "in-flight"),
            (AckStatus.ready, "unknown", "ignored"),
        ]
    ]
    state = SchedulerState(queue=queue)
    assert state.queued_cases == {"assessment"}
    assert state.queued_repairs == {"repair"}
    assert not state.stopped.is_set()
    assert not state.lock.locked()
    other = SchedulerState(queue=queue)
    state.queued_cases.add("new")
    state.stopped.set()
    assert "new" not in other.queued_cases
    assert not other.stopped.is_set()
