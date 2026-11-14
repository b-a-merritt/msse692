from sqlmodel import Session

from conversation_monitor.schemas.observation import ObservationInput
from conversation_monitor.services.observation.records import to_row


def stage_correction(
    *, observation: ObservationInput, speaker_revision_id: int, session: Session
) -> None:
    """Add revised speech without committing; it has a revision instead of a sequence."""
    session.add(to_row(observation=observation, speaker_revision_id=speaker_revision_id))
