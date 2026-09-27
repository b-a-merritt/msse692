import json

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from normative_conformance.errors import StorageUnavailable
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.model import ModelVersion


def evaluate_model(
    *,
    model: ModelVersion,
    case_id: str,
    subject_speaker_id: str,
    through_sequence: int,
    session: Session,
    after_observation: Observation | None = None,
    deadline_at_us: int | None = None,
    observation_sequence: int | None = None,
) -> bool:
    parameters = {
        **{
            key: json.dumps(value) if isinstance(value, list) else value
            for key, value in model.parameters.items()
        },
        "case_id": case_id,
        "subject_speaker_id": subject_speaker_id,
        "through_sequence": through_sequence,
        "after_start_at_us": after_observation.start_at_us if after_observation else None,
        "after_end_at_us": after_observation.end_at_us if after_observation else None,
        "after_sequence": after_observation.sequence if after_observation else None,
        "deadline_at_us": deadline_at_us,
        "observation_sequence": observation_sequence,
    }
    try:
        for rule in model.rules:
            result = session.exec(text(rule.sql), params=parameters)  # type: ignore[call-overload]
            if result.first() is None:
                return False
        return True
    except SQLAlchemyError as error:
        raise StorageUnavailable("The model could not be evaluated") from error
