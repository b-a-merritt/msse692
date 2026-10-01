import logging
from uuid import UUID

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from normative_conformance.database import write_session
from normative_conformance.errors import StorageUnavailable
from normative_conformance.models.assessment import Assessment
from normative_conformance.schemas.assessment import CaseSnapshot
from normative_conformance.schemas.internal import Clock
from normative_conformance.services.assessment.assess_model import assess_model
from normative_conformance.services.assessment.get_last_repair import get_last_repair
from normative_conformance.services.assessment.list_assessments import list_assessments
from normative_conformance.services.model.get_subject_speaker_id import get_subject_speaker_id
from normative_conformance.services.model.list_models import list_models
from normative_conformance.services.observation.get_case_sequence import get_case_sequence
from normative_conformance.services.scheduler.request_repair_check import request_repair_check
from normative_conformance.services.scheduler.state import SchedulerState
from normative_conformance.timestamps import to_microseconds

logger = logging.getLogger(__name__)


def evaluate_case(
    *,
    case_id: str,
    evaluation_id: UUID,
    engine: Engine,
    now: Clock,
    scheduler: SchedulerState,
) -> list[Assessment]:
    """Detect undesired matches, preserving an existing occurrence and its deadline."""
    try:
        with write_session(engine=engine) as session:
            snapshot = CaseSnapshot(
                case_id=case_id,
                evaluation_id=str(evaluation_id),
                through_sequence=get_case_sequence(case_id=case_id, session=session),
                evaluated_at_us=to_microseconds(value=now()),
            )

            results = list_assessments(
                case_id=case_id,
                evaluation_id=snapshot.evaluation_id,
                session=session,
            )

            # A retry reuses its saved results and still reaches repair scheduling below.
            replayed = bool(results)
            if not replayed:
                last_repair = get_last_repair(case_id=case_id, session=session)
                subject_speaker_id = get_subject_speaker_id(session=session)

                for model in list_models(session=session):
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

            session.commit()
    except (SQLAlchemyError, StorageUnavailable) as error:
        logger.exception(
            "Case evaluation rolled back",
            extra={
                "event": "evaluation.rolled_back",
                "case_id": case_id,
                "evaluation_id": str(evaluation_id),
            },
        )
        if isinstance(error, StorageUnavailable):
            raise
        raise StorageUnavailable("The case could not be assessed") from error

    # Existing resolutions still need checks for later repairs that reset detection.
    needs_repair_check = any(
        row.status == "pending" or row.resolves_assessment_id is not None for row in results
    )
    logger.info(
        "Saved evaluation replayed" if replayed else "Case evaluation committed",
        extra={
            "event": "evaluation.replayed" if replayed else "evaluation.committed",
            "case_id": case_id,
            "evaluation_id": snapshot.evaluation_id,
            "through_sequence": snapshot.through_sequence,
            "evaluated_at_us": snapshot.evaluated_at_us,
            "assessment_ids": [row.assessment_id for row in results],
            "repair_check_needed": needs_repair_check,
        },
    )
    if needs_repair_check and not scheduler.stopped.is_set():
        request_repair_check(case_id=case_id, scheduler=scheduler)

    return results
