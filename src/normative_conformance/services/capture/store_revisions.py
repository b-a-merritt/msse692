"""Retain revised speaker attribution without changing observations or decisions."""

import json

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from normative_conformance.database import write_session
from normative_conformance.errors import CaptureFailure
from normative_conformance.models.speaker_revision import SpeakerRevision
from normative_conformance.schemas.internal import Clock
from normative_conformance.schemas.observation import ObservationReplacement
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
                session.add(
                    SpeakerRevision(
                        case_id=case_id,
                        received_at_us=received_at_us,
                        replaced_observation_ids_json=json.dumps(
                            replacement.replaced_observation_ids
                        ),
                        observations_json=json.dumps(
                            [row.model_dump(mode="json") for row in replacement.observations]
                        ),
                    )
                )
            session.commit()
    except SQLAlchemyError as error:
        raise CaptureFailure("storageUnavailable") from error
