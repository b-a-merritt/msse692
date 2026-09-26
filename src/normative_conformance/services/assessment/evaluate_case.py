from uuid import UUID

from sqlalchemy import Engine
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import col
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
from normative_conformance.services.model.list_models import list_models
from normative_conformance.services.scheduler.request_repair_check import request_repair_check
from normative_conformance.services.scheduler.state import SchedulerState
from normative_conformance.timestamps import to_microseconds


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
            through_sequence = session.exec(
                select(func.max(Observation.sequence)).where(
                    Observation.case_id == case_id,
                )
            ).one()
            if through_sequence is None:
                raise NotFound("The case has no observations")
            results = list(
                session.exec(
                    select(Assessment).where(
                        Assessment.evaluation_id == str(evaluation_id),
                        Assessment.case_id == case_id,
                    )
                ).all()
            )
            if not results:
                after = get_last_repair(case_id=case_id, session=session)
                pending = {
                    (row.model_id, row.model_version): row
                    for row in list_pending(case_id=case_id, session=session)
                }
                for model in list_models(session=session).items:
                    if model.type != "undesired":
                        continue
                    if (model.model_id, model.version) in pending:
                        results.append(pending[(model.model_id, model.version)])
                        continue
                    if not evaluate_model(
                        model=model,
                        case_id=case_id,
                        through_sequence=through_sequence,
                        session=session,
                        after_observation=after,
                    ):
                        continue
                    latest = session.exec(
                        select(Assessment)
                        .where(
                            Assessment.case_id == case_id,
                            Assessment.model_id == model.model_id,
                            Assessment.model_version == model.version,
                        )
                        .order_by(col(Assessment.assessment_id).desc())
                        .limit(1)
                    ).first()
                    if latest is not None and latest.status == "conformant":
                        original = (
                            session.get(Assessment, latest.resolves_assessment_id)
                            if latest.resolves_assessment_id is not None
                            else latest
                        )
                        assert original is not None
                        if evaluate_model(
                            model=model,
                            case_id=case_id,
                            through_sequence=original.through_sequence,
                            session=session,
                            after_observation=after,
                        ):
                            results.append(latest)
                            continue
                    evaluated_at_us = to_microseconds(value=now())
                    results.append(
                        create_assessment(
                            model=model,
                            case_id=case_id,
                            evaluation_id=evaluation_id,
                            through_sequence=through_sequence,
                            evaluated_at_us=evaluated_at_us,
                            status="pending" if model.repairable else "conformant",
                            session=session,
                            next_due_at_us=evaluated_at_us + 10_000_000
                            if model.repairable
                            else None,
                        )
                    )
            session.commit()
    except SQLAlchemyError as error:
        raise StorageUnavailable("The case could not be assessed") from error

    if not scheduler.stopped.is_set() and any(
        row.status == "pending" or row.resolves_assessment_id is not None for row in results
    ):
        request_repair_check(case_id=case_id, scheduler=scheduler)
    return results
