from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance.models.observation import Observation


def get_case_history(*, case_id: str, through_sequence: int, session: Session) -> list[Observation]:
    """Read a case's stored observations through an inclusive sequence cutoff."""
    query = (
        select(Observation)
        .where(Observation.case_id == case_id, Observation.sequence <= through_sequence)
        .order_by(col(Observation.sequence))
    )
    return list(session.exec(query).all())
