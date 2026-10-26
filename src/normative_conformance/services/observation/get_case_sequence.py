from sqlalchemy import func
from sqlmodel import Session
from sqlmodel import select

from normative_conformance.models.observation import Observation


def get_case_sequence(
    *,
    case_id: str,
    session: Session,
) -> int:
    """Return the case's last committed observation sequence, or 0 before any speech."""
    sequence = session.exec(
        select(func.max(Observation.sequence)).where(Observation.case_id == case_id)
    ).one()
    return sequence or 0
