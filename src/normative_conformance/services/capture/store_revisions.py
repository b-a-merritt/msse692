"""Retain revised speaker attribution without changing observations or decisions."""

from sqlalchemy import Engine
from sqlalchemy import insert
from sqlalchemy import literal
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance.database import write_session
from normative_conformance.errors import CaptureFailure
from normative_conformance.models.observation import Observation
from normative_conformance.models.speaker_revision import ReplacedObservation
from normative_conformance.models.speaker_revision import SpeakerRevision
from normative_conformance.schemas.internal import Clock
from normative_conformance.schemas.observation import ObservationReplacement
from normative_conformance.services.observation.records import to_row
from normative_conformance.timestamps import to_microseconds


def store_revisions(
    *,
    case_id: str,
    replacements: list[ObservationReplacement],
    engine: Engine,
    now: Clock,
) -> None:
    """Append a batch of observation replacements atomically, including repeated revisions."""
    if not replacements:
        return
    try:
        with write_session(engine=engine) as session:
            session.connection()
            received_at_us = to_microseconds(value=now())
            for replacement in replacements:
                _stage_replacement(
                    session=session,
                    case_id=case_id,
                    received_at_us=received_at_us,
                    replacement=replacement,
                )
            session.commit()
    except SQLAlchemyError as error:
        raise CaptureFailure("storageUnavailable") from error


def _stage_replacement(
    *,
    session: Session,
    case_id: str,
    received_at_us: int,
    replacement: ObservationReplacement,
) -> None:
    revision = SpeakerRevision(case_id=case_id, received_at_us=received_at_us)
    session.add(revision)
    session.flush()

    session.execute(
        insert(ReplacedObservation).from_select(
            ["speaker_revision_id", "observation_key"],
            select(literal(revision.speaker_revision_id), Observation.observation_key).where(
                Observation.case_id == case_id,
                col(Observation.observation_id).in_(replacement.replaced_observation_ids),
                col(Observation.speaker_revision_id).is_(None),
            ),
        )
    )
    session.add_all(
        [
            to_row(observation=row, speaker_revision_id=revision.speaker_revision_id)
            for row in replacement.observations
        ]
    )
