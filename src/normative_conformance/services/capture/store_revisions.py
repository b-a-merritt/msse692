"""Retain revised speaker attribution without changing observations or decisions."""

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from normative_conformance.database import write_session
from normative_conformance.errors import CaptureFailure
from normative_conformance.models.speaker_revision import ReplacedObservation
from normative_conformance.models.speaker_revision import SpeakerRevision
from normative_conformance.schemas.internal import Clock
from normative_conformance.schemas.observation import ObservationReplacement
from normative_conformance.services.observation.load_case_speech import load_case_speech
from normative_conformance.services.observation.stage_correction import stage_correction
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
            # Only ingested speech can be replaced; revised speech is never ingested.
            keys = {
                row.observation.observation_id: row.observation_key
                for row in load_case_speech(case_id=case_id, session=session)
            }
            for replacement in replacements:
                _stage_replacement(
                    session=session,
                    case_id=case_id,
                    received_at_us=received_at_us,
                    replacement=replacement,
                    keys=keys,
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
    keys: dict[str, int],
) -> None:
    revision = SpeakerRevision(case_id=case_id, received_at_us=received_at_us)
    session.add(revision)
    session.flush()

    assert revision.speaker_revision_id is not None
    session.add_all(
        [
            ReplacedObservation(
                speaker_revision_id=revision.speaker_revision_id, observation_key=keys[replaced]
            )
            for replaced in replacement.replaced_observation_ids
            if replaced in keys
        ]
    )
    for row in replacement.observations:
        stage_correction(
            observation=row, speaker_revision_id=revision.speaker_revision_id, session=session
        )
