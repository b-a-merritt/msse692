from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance.models.observation import Observation


def speaker_labels(*, case_id: str, session: Session) -> list[str]:
    """Use speech order, with stable tie breakers for overlapping observations."""
    return list(
        session.exec(
            select(Observation.speaker_id)
            .where(Observation.case_id == case_id, col(Observation.sequence).is_not(None))
            .order_by(
                col(Observation.start_at_us), col(Observation.end_at_us), col(Observation.sequence)
            )
        ).all()
    )
