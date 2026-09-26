from uuid import UUID

from sqlalchemy import Engine
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select

from normative_conformance.database import write_session
from normative_conformance.errors import NotFound
from normative_conformance.errors import StorageUnavailable
from normative_conformance.models.assessment import Assessment
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.internal import Clock
from normative_conformance.services.assessment.create_assessment import create_assessment
from normative_conformance.services.assessment.get_last_repair import get_last_repair
from normative_conformance.services.assessment.list_pending import list_pending
from normative_conformance.services.model.evaluate_model import evaluate_model
from normative_conformance.services.model.find_repair import find_repair
from normative_conformance.services.model.get_model import get_model
from normative_conformance.services.model.list_models import list_models
from normative_conformance.services.scheduler.request_assessment import request_assessment
from normative_conformance.services.scheduler.state import SchedulerState
from normative_conformance.timestamps import to_microseconds


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
            through_sequence = session.exec(
                select(func.max(Observation.sequence)).where(
                    Observation.case_id == case_id,
                )
            ).one()
            if through_sequence is None:
                raise NotFound("The case has no observations")
            evaluated_at_us = to_microseconds(value=now())
            repairs = [
                model for model in list_models(session=session).items if model.type == "repairs"
            ]
            results = []
            last_repair = get_last_repair(case_id=case_id, session=session)
            latest = find_repair(
                models=repairs,
                case_id=case_id,
                through_sequence=through_sequence,
                session=session,
                after_observation=last_repair,
            )
            if latest:
                repair_model, observation = latest
                results.append(
                    create_assessment(
                        model=repair_model,
                        case_id=case_id,
                        evaluation_id=evaluation_id,
                        through_sequence=observation.sequence,
                        evaluated_at_us=evaluated_at_us,
                        status="conformant",
                        session=session,
                        observation_ids=[observation.observation_id],
                    )
                )
            for pending in list_pending(case_id=case_id, session=session):
                model = get_model(
                    model_id=pending.model_id, version=pending.model_version, session=session
                )
                repair = find_repair(
                    models=repairs,
                    case_id=case_id,
                    through_sequence=through_sequence,
                    session=session,
                    deadline_at_us=pending.next_due_at_us,
                )
                # Recheck the original snapshot after the repair's source boundary.
                # This associates a boolean repair rule with the behavior it can cancel.
                repaired = repair is not None and not evaluate_model(
                    model=model,
                    case_id=case_id,
                    through_sequence=pending.through_sequence,
                    session=session,
                    after_observation=repair[1],
                )
                assert pending.next_due_at_us is not None
                if not repaired and evaluated_at_us < pending.next_due_at_us:
                    results.append(pending)
                    continue
                results.append(
                    create_assessment(
                        model=model,
                        case_id=case_id,
                        evaluation_id=evaluation_id,
                        through_sequence=through_sequence,
                        evaluated_at_us=evaluated_at_us,
                        status="non-conformant" if repaired else "conformant",
                        session=session,
                        resolves_assessment_id=pending.assessment_id,
                        observation_ids=[repair[1].observation_id] if repaired and repair else [],
                    )
                )
            session.commit()
    except SQLAlchemyError as error:
        raise StorageUnavailable("Repairs could not be checked") from error

    if not scheduler.stopped.is_set() and any(
        row.status == "non-conformant"
        or (row.status == "conformant" and row.resolves_assessment_id is None)
        for row in results
    ):
        request_assessment(case_id=case_id, scheduler=scheduler)
    return results
