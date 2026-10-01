from collections import defaultdict

from normative_conformance.models.assessment import Assessment


def find_earliest_repair_deadlines(*, assessments: list[Assessment]) -> dict[str, int]:
    """Return each case's earliest non-null repair deadline without changing assessments"""
    deadlines_by_case: dict[str, list[int]] = defaultdict(list)
    for assessment in assessments:
        due_at_us = assessment.next_due_at_us
        if due_at_us is not None:
            deadlines_by_case[assessment.case_id].append(due_at_us)

    return {case_id: min(deadlines) for case_id, deadlines in deadlines_by_case.items()}
