from typing import Literal

from sqlmodel import Session

from normative_conformance.models.assessment import Assessment
from normative_conformance.schemas.assessment import CaseSnapshot
from normative_conformance.schemas.assessment import Explanation
from normative_conformance.schemas.assessment import RuleResult
from normative_conformance.schemas.model import ModelVersion
from normative_conformance.timestamps import from_microseconds

_EXPLANATIONS: dict[str, tuple[str, str, Literal["pending", "satisfied", "not_satisfied"]]] = {
    "pending": ("awaiting_repair", "Awaiting repair", "pending"),
    "conformant": ("matched", "The model matched", "satisfied"),
    "non-conformant": ("repaired", "The pending match was repaired", "not_satisfied"),
}


def create_assessment(
    *,
    model: ModelVersion,
    snapshot: CaseSnapshot,
    status: Literal["pending", "conformant", "non-conformant"],
    session: Session,
    next_due_at_us: int | None = None,
    resolves_assessment_id: int | None = None,
    observation_ids: list[str] | None = None,
) -> Assessment:
    """Append a result and its explanation without committing the caller's transaction."""
    reason_code, reason, outcome = _EXPLANATIONS[status]
    deadline = from_microseconds(value=next_due_at_us) if next_due_at_us is not None else None
    explanation = Explanation(
        reason_code=reason_code,
        summary=reason,
        rules=[
            RuleResult(
                rule_id=rule.rule_id,
                outcome=outcome,
                reason=reason,
                observation_ids=observation_ids or [],
                deadline_at=deadline,
            )
            for rule in model.rules
        ],
    )
    row = Assessment(
        evaluation_id=snapshot.evaluation_id,
        case_id=snapshot.case_id,
        model_id=model.model_id,
        model_version=model.version,
        through_sequence=snapshot.through_sequence,
        evaluated_at_us=snapshot.evaluated_at_us,
        status=status,
        explanation_json=explanation.model_dump_json(),
        next_due_at_us=next_due_at_us,
        resolves_assessment_id=resolves_assessment_id,
    )
    session.add(row)
    session.flush()
    return row
