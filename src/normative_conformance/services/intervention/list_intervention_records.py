from typing import Literal

from sqlmodel import Session

from normative_conformance.schemas.intervention import Intervention
from normative_conformance.services.intervention.list_interventions import list_interventions
from normative_conformance.timestamps import from_microseconds


def list_intervention_records(
    *,
    session: Session,
    case_id: str | None = None,
    status: Literal["pending", "sent"] | None = None,
    intervention_ids: list[int] | None = None,
) -> list[Intervention]:
    """Build API records from stored interventions and their source assessments."""
    records = []
    for row, row_case_id, speaker_id in list_interventions(
        session=session, case_id=case_id, status=status, intervention_ids=intervention_ids
    ):
        assert row.intervention_id is not None and speaker_id is not None
        records.append(
            Intervention(
                intervention_id=row.intervention_id,
                case_id=row_case_id,
                target_speaker_id=speaker_id,
                assessment_id=row.assessment_id,
                message=row.message,
                created_at=from_microseconds(value=row.created_at_us),
                status="pending" if row.sent_at_us is None else "sent",
                sent_at=(
                    from_microseconds(value=row.sent_at_us) if row.sent_at_us is not None else None
                ),
            )
        )
    return records
