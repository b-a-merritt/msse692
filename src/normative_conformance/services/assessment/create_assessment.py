from typing import Literal
from uuid import UUID

from sqlmodel import Session

from normative_conformance.models.assessment import Assessment
from normative_conformance.schemas.assessment import Explanation
from normative_conformance.schemas.assessment import RuleResult
from normative_conformance.schemas.model import ModelVersion
from normative_conformance.timestamps import from_microseconds


def create_assessment(
    *,
    model: ModelVersion,
    case_id: str,
    evaluation_id: UUID,
    through_sequence: int,
    evaluated_at_us: int,
    status: Literal["pending", "conformant", "non-conformant"],
    session: Session,
    next_due_at_us: int | None = None,
    resolves_assessment_id: int | None = None,
    observation_ids: list[str] | None = None,
) -> Assessment:
    reason = {
        "pending": "Awaiting repair",
        "conformant": "The model matched",
        "non-conformant": "The pending match was repaired",
    }[status]
    explanation = Explanation(
        reason_code={
            "pending": "awaiting_repair",
            "conformant": "matched",
            "non-conformant": "repaired",
        }[status],
        summary=reason,
        rules=[
            RuleResult(
                rule_id=rule.rule_id,
                outcome="pending"
                if status == "pending"
                else ("not_satisfied" if status == "non-conformant" else "satisfied"),
                reason=reason,
                observation_ids=observation_ids or [],
                deadline_at=from_microseconds(value=next_due_at_us)
                if next_due_at_us is not None
                else None,
            )
            for rule in model.rules
        ],
    )
    row = Assessment(
        evaluation_id=str(evaluation_id),
        case_id=case_id,
        model_id=model.model_id,
        model_version=model.version,
        through_sequence=through_sequence,
        evaluated_at_us=evaluated_at_us,
        status=status,
        explanation_json=explanation.model_dump_json(),
        next_due_at_us=next_due_at_us,
        resolves_assessment_id=resolves_assessment_id,
    )
    session.add(row)
    session.flush()
    return row
