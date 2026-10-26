from sqlmodel import Session

from normative_conformance.models.assessment import Assessment
from normative_conformance.schemas.assessment import CaseSnapshot
from normative_conformance.schemas.model import ModelVersion
from normative_conformance.services.assessment.assess_model import assess_model
from normative_conformance.services.assessment.get_last_repair import get_last_repair


def evaluate_case(
    *,
    snapshot: CaseSnapshot,
    subject_speaker_id: str,
    session: Session,
    models: list[ModelVersion],
) -> list[Assessment]:
    """Stage detections in the caller's transaction, preserving active occurrences."""
    last_repair = get_last_repair(case_id=snapshot.case_id, session=session)
    results = []
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
