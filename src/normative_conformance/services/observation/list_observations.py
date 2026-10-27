from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance.models.observation import Observation
from normative_conformance.schemas.observation import ObservationRecord
from normative_conformance.services.observation.records import to_record


def list_observations(
    *,
    case_id: str,
    session: Session,
) -> list[ObservationRecord]:
    query = (
        select(Observation)
        .where(
            Observation.case_id == case_id,
            col(Observation.speaker_revision_id).is_(None),
        )
        .order_by(
            col(Observation.sequence).desc(),
        )
    )
    return [to_record(observation=observation) for observation in session.exec(query)]
