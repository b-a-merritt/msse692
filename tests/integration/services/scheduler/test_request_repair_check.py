from normative_conformance.services.scheduler.request_assessment import request_assessment
from normative_conformance.services.scheduler.request_repair_check import request_repair_check
from normative_conformance.services.scheduler.state import SchedulerState


def test_repair_checks_deduplicate_independently_of_assessment_requests(*, assessment_queue):
    scheduler = SchedulerState(queue=assessment_queue)

    request_assessment(case_id="case", scheduler=scheduler)
    request_repair_check(case_id="case", scheduler=scheduler)
    request_repair_check(case_id="case", scheduler=scheduler)
    assert scheduler.queue.qsize() == 2
    assert scheduler.queue.get(block=False)["kind"] == "assess_case"
    assert scheduler.queue.get(block=False)["kind"] == "check_repairs"


def test_waiting_repair_checks_are_restored(*, assessment_queue):
    scheduler = SchedulerState(queue=assessment_queue)

    request_repair_check(case_id="case", scheduler=scheduler)
    reopened_state = SchedulerState(queue=assessment_queue)
    assert reopened_state.queued_cases == set()
    assert reopened_state.queued_repairs == {"case"}
    request_repair_check(case_id="case", scheduler=reopened_state)
    assert assessment_queue.qsize() == 1
