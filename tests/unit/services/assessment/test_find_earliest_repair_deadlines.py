from normative_conformance import models
from normative_conformance.services.assessment.find_earliest_repair_deadlines import (
    find_earliest_repair_deadlines,
)


def test_earliest_deadlines_are_independent_of_order_and_case():
    assessments = [
        models.Assessment(
            case_id=case_id,
            evaluation_id="evaluation",
            model_id="harm_phrase",
            model_version="1",
            through_sequence=1,
            status="conformant",
            evaluated_at_us=100_000_000,
            next_due_at_us=deadline,
            explanation_json="{}",
        )
        for case_id, deadline in [
            ("case", 20),
            ("case", 10),
            ("case", 30),
            ("case", None),
            ("other", 0),
            ("other", 5),
        ]
    ]
    original = [assessment.model_dump() for assessment in assessments]

    assert find_earliest_repair_deadlines(assessments=assessments) == {"case": 10, "other": 0}
    assert find_earliest_repair_deadlines(assessments=list(reversed(assessments))) == {
        "case": 10,
        "other": 0,
    }
    assert [assessment.model_dump() for assessment in assessments] == original


def test_no_deadlines_returns_an_empty_mapping():
    assert find_earliest_repair_deadlines(assessments=[]) == {}
    assert (
        find_earliest_repair_deadlines(
            assessments=[
                models.Assessment(
                    case_id="case",
                    evaluation_id="evaluation",
                    model_id="harm_phrase",
                    model_version="1",
                    through_sequence=1,
                    status="conformant",
                    evaluated_at_us=100_000_000,
                    next_due_at_us=None,
                    resolves_assessment_id=None,
                    explanation_json="{}",
                )
            ]
        )
        == {}
    )
