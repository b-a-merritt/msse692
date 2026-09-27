from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance.models.observation import Observation
from normative_conformance.schemas.common import ListResponse
from normative_conformance.schemas.observation import ObservationRecord
from normative_conformance.timestamps import from_microseconds


def list_observations(
    *,
    case_id: str,
    session: Session,
) -> ListResponse[ObservationRecord]:
    query = (
        select(Observation)
        .where(
            Observation.case_id == case_id,
        )
        .order_by(
            col(Observation.sequence).desc(),
        )
    )
    resolved = session.exec(query).all()
    records = [
        ObservationRecord(
            case_id=observation.case_id,
            observation_id=observation.observation_id,
            speaker_id=observation.speaker_id,
            start_at=from_microseconds(value=observation.start_at_us),
            end_at=from_microseconds(value=observation.end_at_us),
            transcript=observation.transcript,
            signal_level_min=observation.signal_level_min,
            signal_level_avg=observation.signal_level_avg,
            signal_level_max=observation.signal_level_max,
            received_at=from_microseconds(value=observation.received_at_us),
            sequence=observation.sequence,
        )
        for observation in resolved
    ]

    return ListResponse[ObservationRecord](items=records)
