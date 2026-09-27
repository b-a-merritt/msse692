from datetime import timezone

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session
from sqlmodel import select

from normative_conformance.errors import EnqueueFailed
from normative_conformance.errors import ObservationExists
from normative_conformance.errors import StorageUnavailable
from normative_conformance.models.case import CaseLog
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.internal import Clock
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.schemas.observation import ObservationRecord
from normative_conformance.services.scheduler.request_assessment import request_assessment
from normative_conformance.services.scheduler.state import SchedulerState
from normative_conformance.timestamps import to_microseconds


def _check_uniqueness(
    *,
    case_id: str,
    observation_id: str,
    session: Session,
) -> None:
    if session.get(Observation, (case_id, observation_id)) is not None:
        raise ObservationExists("An observation with this identity already exists")


def _create_case_if_missing(
    *,
    case_id: str,
    received_at_us: int,
    session: Session,
) -> None:
    if session.get(CaseLog, case_id) is None:
        session.add(CaseLog(case_id=case_id, created_at_us=received_at_us))
        session.flush()


def _next_sequence_num(
    *,
    case_id: str,
    session: Session,
) -> int:
    last_sequence = session.exec(
        select(func.max(Observation.sequence)).where(Observation.case_id == case_id)
    ).one()

    return (last_sequence or 0) + 1


def ingest(
    *,
    input: ObservationInput,
    session: Session,
    now: Clock,
    scheduler: SchedulerState,
) -> ObservationRecord:
    """Commit an observation, then request assessment of its case."""
    try:
        # Acquire the writer lock before checking identity or assigning receipt order.
        session.connection()

        received_at = now().astimezone(timezone.utc)
        received_at_us = to_microseconds(value=received_at)

        _check_uniqueness(
            case_id=input.case_id,
            observation_id=input.observation_id,
            session=session,
        )
        _create_case_if_missing(
            case_id=input.case_id,
            received_at_us=received_at_us,
            session=session,
        )

        record = ObservationRecord(
            **input.model_dump(),
            received_at=received_at,
            sequence=_next_sequence_num(case_id=input.case_id, session=session),
        )

        session.add(
            Observation(
                case_id=record.case_id,
                observation_id=record.observation_id,
                sequence=record.sequence,
                received_at_us=received_at_us,
                speaker_id=record.speaker_id,
                start_at_us=to_microseconds(value=record.start_at),
                end_at_us=to_microseconds(value=record.end_at),
                transcript=record.transcript,
                signal_level_min=record.signal_level_min,
                signal_level_avg=record.signal_level_avg,
                signal_level_max=record.signal_level_max,
            )
        )

        session.commit()
    except SQLAlchemyError as error:
        session.rollback()
        raise StorageUnavailable("The observation could not be stored") from error
    except ObservationExists:
        session.rollback()
        raise

    try:
        request_assessment(case_id=record.case_id, scheduler=scheduler)
    except EnqueueFailed as error:
        raise EnqueueFailed(
            message="The observation was stored but its assessment could not be requested",
            committed_observation=record,
        ) from error
    return record
