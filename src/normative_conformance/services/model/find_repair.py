from collections.abc import Sequence

from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance.models.observation import Observation
from normative_conformance.schemas.model import ModelVersion
from normative_conformance.services.model.evaluate_model import evaluate_model


def find_repair(
    *,
    models: Sequence[ModelVersion],
    case_id: str,
    subject_speaker_id: str,
    through_sequence: int,
    session: Session,
    after_observation: Observation | None = None,
    deadline_at_us: int | None = None,
) -> tuple[ModelVersion, Observation] | None:
    query = (
        select(Observation)
        .where(
            Observation.case_id == case_id,
            Observation.sequence <= through_sequence,
        )
        .order_by(
            col(Observation.start_at_us).desc(),
            col(Observation.end_at_us).desc(),
            col(Observation.sequence).desc(),
        )
    )

    for observation in session.exec(query):
        for model in models:
            if evaluate_model(
                model=model,
                case_id=case_id,
                subject_speaker_id=subject_speaker_id,
                through_sequence=through_sequence,
                session=session,
                after_observation=after_observation,
                deadline_at_us=deadline_at_us,
                observation_sequence=observation.sequence,
            ):
                return model, observation

    return None
