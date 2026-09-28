from typing import Literal

from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance.models.intervention import Intervention


def list_interventions(
    *,
    session: Session,
    case_id: str | None = None,
    status: Literal["pending", "sent"] | None = None,
    intervention_ids: list[int] | None = None,
) -> list[Intervention]:
    """List interventions matching the case and delivery status in ID order."""
    query = select(Intervention)

    if case_id is not None:
        query = query.where(Intervention.case_id == case_id)
    if status == "pending":
        query = query.where(col(Intervention.sent_at_us).is_(None))
    elif status == "sent":
        query = query.where(col(Intervention.sent_at_us).is_not(None))
    if intervention_ids is not None:
        query = query.where(col(Intervention.intervention_id).in_(intervention_ids))

    return list(session.exec(query.order_by(col(Intervention.intervention_id))).all())
