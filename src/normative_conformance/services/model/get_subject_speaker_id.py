from sqlmodel import Session

from normative_conformance.errors import NotReady
from normative_conformance.models.case import ExperimentConfig


def get_subject_speaker_id(*, session: Session) -> str:
    """Read the fixed experiment subject for a case operation."""
    config = session.get(ExperimentConfig, 1)
    if config is None:
        raise NotReady("The experiment has not been configured")
    return config.subject_speaker_id
