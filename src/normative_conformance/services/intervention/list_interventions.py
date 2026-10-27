from typing import Literal

from sqlalchemy import and_
from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance.models.assessment import Assessment
from normative_conformance.models.case import TargetAssignment
from normative_conformance.models.intervention import Intervention
from normative_conformance.services.intervention.is_pending import is_pending


def list_interventions(
    *,
    session: Session,
    case_id: str | None = None,
    status: Literal["pending", "sent"] | None = None,
    intervention_ids: list[int] | None = None,
) -> list[tuple[Intervention, str, str | None]]:
    """List interventions with their case and target speaker in ID order."""
    query = (
        select(Intervention, Assessment.case_id, TargetAssignment.speaker_id)
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
    if status == "pending":
        query = query.where(is_pending())
    elif status == "sent":
        query = query.where(col(Intervention.sent_at_us).is_not(None))
    if intervention_ids is not None:
        query = query.where(col(Intervention.intervention_id).in_(intervention_ids))

    return list(session.exec(query.order_by(col(Intervention.intervention_id))).all())
