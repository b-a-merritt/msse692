from uuid import UUID

from sqlmodel import Session

from normative_conformance.models.assessment import Assessment
from normative_conformance.schemas.assessment import CaseSnapshot
from normative_conformance.schemas.internal import Clock
from normative_conformance.schemas.model import ModelVersion
from normative_conformance.services.assessment.assess_model import assess_model
from normative_conformance.services.assessment.get_last_repair import get_last_repair
from normative_conformance.services.model.get_subject_speaker_id import get_subject_speaker_id
from normative_conformance.services.observation.get_case_sequence import get_case_sequence
from normative_conformance.timestamps import to_microseconds


def evaluate_case(
    *,
    case_id: str,
    evaluation_id: UUID,
    session: Session,
    now: Clock,
    models: list[ModelVersion],
) -> list[Assessment]:
    """Stage detections in the caller's transaction, preserving active occurrences."""
    subject_speaker_id = get_subject_speaker_id(case_id=case_id, session=session)
    if subject_speaker_id is None:
        return []
    snapshot = CaseSnapshot(
        case_id=case_id,
        evaluation_id=str(evaluation_id),
        through_sequence=get_case_sequence(case_id=case_id, session=session),
        evaluated_at_us=to_microseconds(value=now()),
    )

    results = []
    last_repair = get_last_repair(case_id=case_id, session=session)

    for model in models:
        if model.type != "undesired":
            continue
        result = assess_model(
            model=model,
            snapshot=snapshot,
            subject_speaker_id=subject_speaker_id,
            last_repair=last_repair,
            session=session,
        )
        if result is not None:
            results.append(result)

    return results
