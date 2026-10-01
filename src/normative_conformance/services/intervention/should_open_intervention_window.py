from typing import Literal

from normative_conformance.models.assessment import Assessment


def should_open_intervention_window(
    *,
    assessments: list[Assessment],
    task_kind: Literal["assess_case", "check_repairs"],
    evaluation_id: str,
    started_at_us: int,
) -> bool:
    """Check for a new undesired confirmation without changing assessments or windows"""
    return any(
        assessment.status == "conformant"
        and assessment.evaluation_id == evaluation_id
        and assessment.evaluated_at_us >= started_at_us
        and (task_kind == "assess_case" or assessment.resolves_assessment_id is not None)
        for assessment in assessments
    )
