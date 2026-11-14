from sqlalchemy import and_
from sqlalchemy import case
from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from conversation_monitor.models.assessment import Assessment
from conversation_monitor.models.case import TargetAssignment
from conversation_monitor.models.intervention import Intervention
from conversation_monitor.schemas.internal import Clock
from conversation_monitor.schemas.intervention import InterventionStatus
from conversation_monitor.services.intervention.is_pending import is_pending
from conversation_monitor.timestamps import to_microseconds


def list_interventions(
    *,
    session: Session,
    case_id: str | None = None,
    status: InterventionStatus | None = None,
    intervention_ids: list[int] | None = None,
    now: Clock,
) -> list[tuple[Intervention, str, str | None, InterventionStatus]]:
    """List interventions with their case, target speaker, and status in ID order.

    An unsent intervention that is no longer pending has expired.
    """
    status_at_now = case(
        (col(Intervention.sent_at_us).is_not(None), "sent"),
        (is_pending(now_us=to_microseconds(value=now())), "pending"),
        else_="expired",
    )
    query = (
        select(Intervention, Assessment.case_id, TargetAssignment.speaker_id, status_at_now)
        .select_from(Intervention)
        .join(Assessment)
        .join(
            TargetAssignment,
            and_(
                col(TargetAssignment.case_id) == Assessment.case_id,
                col(TargetAssignment.target_revision) == Assessment.target_revision,
            ),
        )
    )

    if case_id is not None:
        query = query.where(Assessment.case_id == case_id)
    if status is not None:
        query = query.where(status_at_now == status)
    if intervention_ids is not None:
        query = query.where(col(Intervention.intervention_id).in_(intervention_ids))

    return list(session.exec(query.order_by(col(Intervention.intervention_id))).all())
