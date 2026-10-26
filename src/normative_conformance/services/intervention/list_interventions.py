from typing import Literal

from sqlalchemy import ColumnElement
from sqlalchemy import and_
from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance.models.intervention import Intervention
from normative_conformance.services.case.target import for_current_target


def is_pending() -> ColumnElement[bool]:
    """Match undelivered interventions whose target mapping is still current."""
    return and_(col(Intervention.sent_at_us).is_(None), for_current_target(Intervention))


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
        query = query.where(is_pending())
    elif status == "sent":
        query = query.where(col(Intervention.sent_at_us).is_not(None))
    if intervention_ids is not None:
        query = query.where(col(Intervention.intervention_id).in_(intervention_ids))

    return list(session.exec(query.order_by(col(Intervention.intervention_id))).all())
