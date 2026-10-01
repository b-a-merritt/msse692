from normative_conformance.services.assessment.find_earliest_repair_deadlines import (
    find_earliest_repair_deadlines,
)


def test_earliest_deadlines_are_independent_of_order_and_case(*, assessment_result):
    assessments = [
        assessment_result(next_due_at_us=20),
        assessment_result(next_due_at_us=10),
        assessment_result(next_due_at_us=30),
        assessment_result(),
        assessment_result(case_id="other", next_due_at_us=0),
        assessment_result(case_id="other", next_due_at_us=5),
    ]
    original = [assessment.model_dump() for assessment in assessments]

    assert find_earliest_repair_deadlines(assessments=assessments) == {"case": 10, "other": 0}
    assert find_earliest_repair_deadlines(assessments=list(reversed(assessments))) == {
        "case": 10,
        "other": 0,
    }
    assert [assessment.model_dump() for assessment in assessments] == original


def test_no_deadlines_returns_an_empty_mapping(*, assessment_result):
    assert find_earliest_repair_deadlines(assessments=[]) == {}
    assert find_earliest_repair_deadlines(assessments=[assessment_result()]) == {}
