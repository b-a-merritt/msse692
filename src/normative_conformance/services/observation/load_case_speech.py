from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance.models.observation import Observation
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.services.observation.records import to_input
from normative_conformance.timestamps import from_microseconds


@dataclass(frozen=True)
class IngestedObservation:
    observation_key: int
    sequence: int
    received_at: datetime
    observation: ObservationInput


def load_case_speech(*, case_id: str, session: Session) -> list[IngestedObservation]:
    """Read a case's speech as ingested, in sequence order; speaker corrections are excluded."""
    rows = session.exec(
        select(Observation)
        .where(Observation.case_id == case_id, col(Observation.sequence).is_not(None))
        .order_by(col(Observation.sequence))
    ).all()
    return [_ingested(row) for row in rows]


def _ingested(row: Observation) -> IngestedObservation:
    assert row.observation_key is not None
    assert row.sequence is not None and row.received_at_us is not None
    return IngestedObservation(
        observation_key=row.observation_key,
        sequence=row.sequence,
        received_at=from_microseconds(value=row.received_at_us),
        observation=to_input(observation=row),
    )
