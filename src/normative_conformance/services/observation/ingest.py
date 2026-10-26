import logging
from datetime import timezone

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session
from sqlmodel import select

from normative_conformance.errors import ObservationExists
from normative_conformance.errors import StorageUnavailable
from normative_conformance.models.case import CaseLog
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.internal import Clock
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.schemas.observation import ObservationRecord
from normative_conformance.services.case.selection import speaker_labels
from normative_conformance.services.case.target import refresh_target
from normative_conformance.services.observation.records import to_record
from normative_conformance.timestamps import to_microseconds

logger = logging.getLogger(__name__)


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
) -> CaseLog:
    case = session.get(CaseLog, case_id)
    if case is None:
        case = CaseLog(case_id=case_id, created_at_us=received_at_us)
        session.add(case)
        session.flush()
    return case


def _next_sequence_num(
    *,
    case_id: str,
    session: Session,
) -> int:
    last_sequence = session.exec(
        select(func.max(Observation.sequence)).where(Observation.case_id == case_id)
    ).one()

    return (last_sequence or 0) + 1


def stage_observation(
    *,
    input: ObservationInput,
    session: Session,
    now: Clock,
) -> ObservationRecord:
    """Insert without committing or rolling back.

    Use a write_session. The caller must commit all related changes together or
    roll back on any failure.
    """
    session.connection()
    received_at_us = to_microseconds(value=now().astimezone(timezone.utc))
    _check_uniqueness(case_id=input.case_id, observation_id=input.observation_id, session=session)
    case = _create_case_if_missing(
        case_id=input.case_id,
        received_at_us=received_at_us,
        session=session,
    )
    observation = Observation(
        case_id=input.case_id,
        observation_id=input.observation_id,
        sequence=_next_sequence_num(case_id=input.case_id, session=session),
        received_at_us=received_at_us,
        updated_at_us=received_at_us,
        speaker_id=input.speaker_id,
        start_at_us=to_microseconds(value=input.start_at),
        end_at_us=to_microseconds(value=input.end_at),
        transcript=input.transcript,
        signal_level_min=input.signal_level_min,
        signal_level_avg=input.signal_level_avg,
        signal_level_max=input.signal_level_max,
    )
    session.add(observation)
    if case.target_speaker_order is not None and not case.target_speaker_manual:
        refresh_target(case=case, labels=speaker_labels(case_id=input.case_id, session=session))
    session.flush()
    return to_record(observation=observation)


def ingest(
    *,
    input: ObservationInput,
    session: Session,
    now: Clock,
) -> ObservationRecord:
    """Commit an observation for database polling."""
    try:
        record = stage_observation(input=input, session=session, now=now)
        session.commit()
    except SQLAlchemyError as error:
        session.rollback()
        logger.exception(
            "Observation rolled back",
            extra={
                "event": "observation.rolled_back",
                "case_id": input.case_id,
                "observation_id": input.observation_id,
            },
        )
        raise StorageUnavailable("The observation could not be stored") from error
    except ObservationExists:
        session.rollback()
        raise

    logger.info(
        "Observation committed",
        extra={
            "event": "observation.committed",
            "case_id": record.case_id,
            "observation_id": record.observation_id,
            "sequence": record.sequence,
        },
    )

    return record
