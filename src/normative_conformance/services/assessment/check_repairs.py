import logging
from dataclasses import replace
from uuid import UUID

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from normative_conformance.database import write_session
from normative_conformance.errors import StorageUnavailable
from normative_conformance.models.assessment import Assessment
from normative_conformance.schemas.assessment import CaseSnapshot
from normative_conformance.schemas.internal import Clock
from normative_conformance.services.assessment.create_assessment import create_assessment
from normative_conformance.services.assessment.get_last_repair import get_last_repair
from normative_conformance.services.assessment.list_assessments import list_assessments
from normative_conformance.services.assessment.resolve_pending import resolve_pending
from normative_conformance.services.model.find_repair import find_repair
from normative_conformance.services.model.get_subject_speaker_id import get_subject_speaker_id
from normative_conformance.services.model.list_models import list_models
from normative_conformance.services.observation.get_case_sequence import get_case_sequence
from normative_conformance.services.scheduler.request_assessment import request_assessment
from normative_conformance.services.scheduler.state import SchedulerState
from normative_conformance.timestamps import to_microseconds

logger = logging.getLogger(__name__)


def check_repairs(
    *,
    case_id: str,
    evaluation_id: UUID,
    engine: Engine,
    now: Clock,
    scheduler: SchedulerState,
) -> list[Assessment]:
    """Record repairs and append one final result for each resolved pending match."""
    try:
        with write_session(engine=engine) as session:
            snapshot = CaseSnapshot(
                case_id=case_id,
                evaluation_id=str(evaluation_id),
                through_sequence=get_case_sequence(case_id=case_id, session=session),
                evaluated_at_us=to_microseconds(value=now()),
            )
            subject_speaker_id = get_subject_speaker_id(session=session)

            models = {
                (model.model_id, model.version): model for model in list_models(session=session)
            }
            repair_models = [model for model in models.values() if model.type == "repairs"]
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
                    model=models[pending.model_id, pending.model_version],
                    repair_models=repair_models,
                    snapshot=snapshot,
                    subject_speaker_id=subject_speaker_id,
                    session=session,
                )
                for pending in list_assessments(
                    case_id=case_id, status="pending", unresolved=True, session=session
                )
            )
            session.commit()
    except (SQLAlchemyError, StorageUnavailable) as error:
        logger.exception(
            "Repair check rolled back",
            extra={
                "event": "repairs.rolled_back",
                "case_id": case_id,
                "evaluation_id": str(evaluation_id),
            },
        )
        if isinstance(error, StorageUnavailable):
            raise
        raise StorageUnavailable("Repairs could not be checked") from error

    needs_assessment = new_repair is not None or any(
        row.status == "non-conformant" for row in results
    )
    logger.info(
        "Repair check committed",
        extra={
            "event": "repairs.committed",
            "case_id": case_id,
            "evaluation_id": snapshot.evaluation_id,
            "through_sequence": snapshot.through_sequence,
            "evaluated_at_us": snapshot.evaluated_at_us,
            "repair_model_id": new_repair[0].model_id if new_repair else None,
            "repair_observation_id": new_repair[1].observation_id if new_repair else None,
            "resolution_ids": [
                row.assessment_id for row in results if row.resolves_assessment_id is not None
            ],
            "reassessment_needed": needs_assessment,
        },
    )
    if needs_assessment and not scheduler.stopped.is_set():
        request_assessment(case_id=case_id, scheduler=scheduler)

    return results
