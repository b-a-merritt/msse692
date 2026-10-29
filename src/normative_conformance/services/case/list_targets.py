from sqlmodel import Session
from sqlmodel import select

from normative_conformance.models.case import TargetAssignment


def list_targets(*, case_id: str, session: Session) -> dict[int, str | None]:
    """Map each of the case's target revisions to its speaker label."""
    return dict(
        session.exec(
            select(TargetAssignment.target_revision, TargetAssignment.speaker_id).where(
                TargetAssignment.case_id == case_id
            )
        ).all()
    )
