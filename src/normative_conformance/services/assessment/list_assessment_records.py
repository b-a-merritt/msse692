from sqlmodel import Session

from normative_conformance import models
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.assessment import Assessment
from normative_conformance.schemas.assessment import Explanation
from normative_conformance.schemas.assessment import Extent
from normative_conformance.services.assessment.list_assessments import list_assessments
from normative_conformance.services.model.get_subject_speaker_id import get_subject_speaker_id
from normative_conformance.services.observation.get_case_history import get_case_history
from normative_conformance.timestamps import from_microseconds


def list_assessment_records(*, case_id: str, session: Session) -> list[Assessment]:
    """Build API records from stored assessments and their evaluated case prefixes."""
    rows = list_assessments(case_id=case_id, session=session)
    if not rows:
        return []

    subject_speaker_id = get_subject_speaker_id(session=session)
    history = get_case_history(
        case_id=case_id,
        through_sequence=max(row.through_sequence for row in rows),
        session=session,
    )

    return [
        _to_record(
            row=row,
            history=history,
            subject_speaker_id=subject_speaker_id,
        )
        for row in rows
    ]


def _to_record(
    *,
    row: models.Assessment,
    history: list[Observation],
    subject_speaker_id: str,
) -> Assessment:
    assert row.assessment_id is not None

    observation_ids = [
        observation.observation_id
        for observation in history
        if observation.sequence <= row.through_sequence
    ]

    return Assessment(
        assessment_id=row.assessment_id,
        resolves_assessment_id=row.resolves_assessment_id,
        evaluation_id=row.evaluation_id,
        case_id=row.case_id,
        subject_speaker_id=subject_speaker_id,
        model_id=row.model_id,
        model_version=row.model_version,
        evaluated_at=from_microseconds(value=row.evaluated_at_us),
        status=row.status,
        extent=Extent(
            through_sequence=row.through_sequence,
            observation_count=len(observation_ids),
            observation_ids=observation_ids,
        ),
        explanation=Explanation.model_validate_json(row.explanation_json),
        next_due_at=(
            from_microseconds(value=row.next_due_at_us) if row.next_due_at_us is not None else None
        ),
    )
