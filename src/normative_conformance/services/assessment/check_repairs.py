from dataclasses import replace
from uuid import UUID

from sqlmodel import Session

from normative_conformance.models.assessment import Assessment
from normative_conformance.schemas.assessment import CaseSnapshot
from normative_conformance.schemas.internal import Clock
from normative_conformance.schemas.model import ModelVersion
from normative_conformance.services.assessment.create_assessment import create_assessment
from normative_conformance.services.assessment.get_last_repair import get_last_repair
from normative_conformance.services.assessment.list_assessments import list_assessments
from normative_conformance.services.assessment.resolve_pending import resolve_pending
from normative_conformance.services.model.find_repair import find_repair
from normative_conformance.services.model.get_subject_speaker_id import get_subject_speaker_id
from normative_conformance.services.observation.get_case_sequence import get_case_sequence
from normative_conformance.timestamps import to_microseconds


def check_repairs(
    *,
    case_id: str,
    evaluation_id: UUID,
    session: Session,
    now: Clock,
    models: list[ModelVersion],
) -> list[Assessment]:
    """Stage repairs and pending resolutions in the caller's write transaction."""
    subject_speaker_id = get_subject_speaker_id(case_id=case_id, session=session)
    if subject_speaker_id is None:
        return []
    snapshot = CaseSnapshot(
        case_id=case_id,
        evaluation_id=str(evaluation_id),
        through_sequence=get_case_sequence(case_id=case_id, session=session),
        evaluated_at_us=to_microseconds(value=now()),
    )

    models_by_version = {(model.model_id, model.version): model for model in models}
    repair_models = [model for model in models if model.type == "repairs"]
    new_repair = find_repair(
        models=repair_models,
        case_id=case_id,
        subject_speaker_id=subject_speaker_id,
        through_sequence=snapshot.through_sequence,
        session=session,
        after_observation=get_last_repair(case_id=case_id, session=session),
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
            case_id=case_id,
            status="pending",
            unresolved=True,
            current_target=True,
            session=session,
        )
    )
    return results
