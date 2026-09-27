from sqlalchemy import func
from sqlmodel import Session
from sqlmodel import select

from normative_conformance.errors import NotFound
from normative_conformance.models.observation import Observation


def get_case_sequence(
    *,
    case_id: str,
    session: Session,
) -> int:
    """Capture the last committed observation included in this evaluation."""
    sequence = session.exec(
        select(func.max(Observation.sequence)).where(Observation.case_id == case_id)
    ).one()

    if sequence is None:
        raise NotFound("The case has no observations")

    return sequence
