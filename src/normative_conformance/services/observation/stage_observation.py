from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance.errors import ObservationExists
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.internal import Clock
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.schemas.observation import ObservationRecord
from normative_conformance.services.case.ensure_case import ensure_case
from normative_conformance.services.case.speaker_labels import speaker_labels
from normative_conformance.services.case.target import refresh_target
from normative_conformance.services.observation.get_case_sequence import get_case_sequence
from normative_conformance.services.observation.records import to_record
from normative_conformance.services.observation.records import to_row
from normative_conformance.timestamps import to_microseconds


def _check_uniqueness(
    *,
    case_id: str,
    observation_id: str,
    session: Session,
) -> None:
    existing = session.exec(
        select(Observation.observation_key).where(
            Observation.case_id == case_id,
            Observation.observation_id == observation_id,
            col(Observation.speaker_revision_id).is_(None),
        )
    ).first()
    if existing is not None:
        raise ObservationExists("An observation with this identity already exists")


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
    received_at_us = to_microseconds(value=now())
    _check_uniqueness(case_id=input.case_id, observation_id=input.observation_id, session=session)
    case = ensure_case(case_id=input.case_id, created_at_us=received_at_us, session=session)
    observation = to_row(
        observation=input,
        sequence=get_case_sequence(case_id=input.case_id, session=session) + 1,
        received_at_us=received_at_us,
    )
    session.add(observation)
    if case.target_speaker_order is not None:
        refresh_target(
            case_id=input.case_id,
            target_speaker_order=case.target_speaker_order,
            labels=speaker_labels(case_id=input.case_id, session=session),
            session=session,
            assigned_at_us=received_at_us,
        )
    session.flush()
    return to_record(observation=observation)
