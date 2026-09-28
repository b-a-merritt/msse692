from typing import Literal

from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance.models.intervention import Intervention as InterventionModel
from normative_conformance.models.intervention import InterventionSource
from normative_conformance.schemas.intervention import Intervention
from normative_conformance.services.intervention.list_interventions import list_interventions
from normative_conformance.services.model.get_subject_speaker_id import get_subject_speaker_id
from normative_conformance.timestamps import from_microseconds


def list_intervention_records(
    *,
    session: Session,
    case_id: str | None = None,
    status: Literal["pending", "sent"] | None = None,
    intervention_ids: list[int] | None = None,
) -> list[Intervention]:
    """Build API records from stored interventions and their sources."""
    rows = list_interventions(
        session=session, case_id=case_id, status=status, intervention_ids=intervention_ids
    )
    if not rows:
        return []

    sources: dict[int, list[int]] = {}
    for source in session.exec(
        select(InterventionSource)
        .where(col(InterventionSource.intervention_id).in_([row.intervention_id for row in rows]))
        .order_by(col(InterventionSource.assessment_id))
    ):
        sources.setdefault(source.intervention_id, []).append(source.assessment_id)

    subject_speaker_id = get_subject_speaker_id(session=session)

    return [
        _to_record(
            row=row,
            subject_speaker_id=subject_speaker_id,
            sources=sources,
        )
        for row in rows
    ]


def _to_record(
    *, row: InterventionModel, subject_speaker_id: str, sources: dict[int, list[int]]
) -> Intervention:
    assert row.intervention_id is not None
    return Intervention(
        intervention_id=row.intervention_id,
        case_id=row.case_id,
        subject_speaker_id=subject_speaker_id,
        assessment_ids=sources[row.intervention_id],
        message=row.message,
        created_at=from_microseconds(value=row.created_at_us),
        status="pending" if row.sent_at_us is None else "sent",
        sent_at=(from_microseconds(value=row.sent_at_us) if row.sent_at_us is not None else None),
    )
