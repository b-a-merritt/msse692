"""Reopening the queue preserves which cases have waiting requests."""

from contextlib import closing

from normative_conformance.queue import create_assessment_queue
from normative_conformance.services.scheduler.request_assessment import request_assessment
from normative_conformance.services.scheduler.state import SchedulerState


def test_reopened_scheduler_reuses_waiting_requests(*, tmp_path):
    path = tmp_path / "queue"
    with closing(create_assessment_queue(path=path)) as queue:
        scheduler = SchedulerState(queue=queue)
        request_assessment(case_id="waiting", scheduler=scheduler)
        request_assessment(case_id="done", scheduler=scheduler)
        request_assessment(case_id="failed", scheduler=scheduler)
        waiting = queue.get(block=False)
        queue.nack(item=waiting)
        done = queue.get(id=2, block=False)
        queue.ack(item=done)
        failed = queue.get(id=3, block=False)
        queue.ack_failed(item=failed)

    with closing(create_assessment_queue(path=path)) as queue:
        scheduler = SchedulerState(queue=queue)
        assert scheduler.queued_cases == {"waiting"}
        request_assessment(case_id="waiting", scheduler=scheduler)
        request_assessment(case_id="done", scheduler=scheduler)
        request_assessment(case_id="failed", scheduler=scheduler)
        assert queue.qsize() == 3
