from dataclasses import replace

from sqlmodel import Session

from normative_conformance.models.assessment import Assessment
from normative_conformance.schemas.assessment import CaseSnapshot
from normative_conformance.schemas.model import ModelVersion
from normative_conformance.services.assessment.create_assessment import create_assessment
from normative_conformance.services.assessment.get_last_repair import get_last_repair
from normative_conformance.services.assessment.list_assessments import list_assessments
from normative_conformance.services.assessment.resolve_pending import resolve_pending
from normative_conformance.services.model.find_repair import find_repair


def check_repairs(
    *,
    snapshot: CaseSnapshot,
    subject_speaker_id: str,
    session: Session,
    models: list[ModelVersion],
) -> list[Assessment]:
    """Stage repairs and pending resolutions in the caller's write transaction."""
    models_by_version = {(model.model_id, model.version): model for model in models}
    repair_models = [model for model in models if model.type == "repairs"]
    new_repair = find_repair(
        models=repair_models,
        case_id=snapshot.case_id,
        subject_speaker_id=subject_speaker_id,
        through_sequence=snapshot.through_sequence,
        session=session,
        after_observation=get_last_repair(case_id=snapshot.case_id, session=session),
    )

    results = []
    if new_repair is not None:
        repair_model, observation = new_repair
        results.append(
            create_assessment(
                model=repair_model,
                snapshot=replace(snapshot, through_sequence=observation.sequence),
                status="conformant",
                session=session,
                observation_ids=[observation.observation_id],
            )
        )

    results.extend(
        resolve_pending(
            pending=pending,
            model=models_by_version[pending.model_id, pending.model_version],
            repair_models=repair_models,
            snapshot=snapshot,
            subject_speaker_id=subject_speaker_id,
            session=session,
        )
        for pending in list_assessments(
            case_id=snapshot.case_id,
            status="pending",
            unresolved=True,
            current_target=True,
            session=session,
        )
    )
    return results
