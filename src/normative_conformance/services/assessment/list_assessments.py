from typing import Literal

from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance.models.assessment import Assessment
from normative_conformance.models.case import CaseLog


def list_assessments(
    *,
    session: Session,
    case_id: str | None = None,
    evaluation_id: str | None = None,
    status: Literal["conformant", "non-conformant", "pending", "conflicted"] | None = None,
    unresolved: bool = False,
    current_target: bool = False,
) -> list[Assessment]:
    """Read stored assessments in ID order, optionally excluding resolved results."""
    query = select(Assessment)

    if current_target:
        query = query.join(CaseLog, col(CaseLog.case_id) == Assessment.case_id).where(
            Assessment.target_revision == CaseLog.target_revision,
            Assessment.subject_speaker_id == CaseLog.target_speaker_id,
        )
    if case_id is not None:
        query = query.where(Assessment.case_id == case_id)
    if evaluation_id is not None:
        query = query.where(Assessment.evaluation_id == evaluation_id)
    if status is not None:
        query = query.where(Assessment.status == status)
    if unresolved:
        resolved = select(Assessment.resolves_assessment_id).where(
            col(Assessment.resolves_assessment_id).is_not(None)
        )
        query = query.where(col(Assessment.assessment_id).not_in(resolved))

    return list(session.exec(query.order_by(col(Assessment.assessment_id))).all())
