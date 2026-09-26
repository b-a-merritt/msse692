from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance.models.assessment import Assessment


def list_pending(*, session: Session, case_id: str | None = None) -> list[Assessment]:
    resolved = select(Assessment.resolves_assessment_id).where(
        col(Assessment.resolves_assessment_id).is_not(None)
    )
    query = select(Assessment).where(
        Assessment.status == "pending", col(Assessment.assessment_id).not_in(resolved)
    )
    if case_id is not None:
        query = query.where(Assessment.case_id == case_id)
    return list(session.exec(query.order_by(col(Assessment.assessment_id))).all())
