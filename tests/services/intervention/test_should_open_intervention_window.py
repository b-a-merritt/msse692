import pytest

from normative_conformance.services.intervention.should_open_intervention_window import (
    should_open_intervention_window,
)


@pytest.mark.parametrize(
    ("task_kind", "changes", "expected"),
    [
        pytest.param("assess_case", {}, True, id="fresh-confirmation"),
        pytest.param(
            "assess_case", {"evaluated_at_us": 100_000_001}, True, id="later-confirmation"
        ),
        pytest.param("assess_case", {"status": "pending"}, False, id="pending"),
        pytest.param("assess_case", {"status": "non-conformant"}, False, id="non-conformant"),
        pytest.param("assess_case", {"evaluation_id": "previous"}, False, id="reused"),
        pytest.param("assess_case", {"evaluated_at_us": 99_999_999}, False, id="replayed"),
        pytest.param("check_repairs", {}, False, id="successful-repair"),
        pytest.param(
            "check_repairs", {"resolves_assessment_id": 1}, True, id="confirmed-after-deadline"
        ),
        pytest.param(
            "check_repairs",
            {"resolves_assessment_id": 1, "status": "non-conformant"},
            False,
            id="repaired-pending-match",
        ),
    ],
)
def test_only_new_undesired_confirmations_qualify(
    *, assessment_result, task_kind, changes, expected
):
    assessment = assessment_result(**changes)
    original = assessment.model_dump()

    assert (
        should_open_intervention_window(
            assessments=[assessment],
            task_kind=task_kind,
            evaluation_id="evaluation",
            started_at_us=100_000_000,
        )
        is expected
    )
    assert assessment.model_dump() == original


def test_one_qualifying_result_is_enough(*, assessment_result):
    assert should_open_intervention_window(
        assessments=[assessment_result(status="pending"), assessment_result()],
        task_kind="assess_case",
        evaluation_id="evaluation",
        started_at_us=100_000_000,
    )


def test_no_results_cannot_open_a_window():
    assert not should_open_intervention_window(
        assessments=[],
        task_kind="assess_case",
        evaluation_id="evaluation",
        started_at_us=100_000_000,
    )
