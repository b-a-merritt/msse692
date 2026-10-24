from sqlmodel import Session

from normative_conformance.errors import NotFound
from normative_conformance.models.case import CaseLog


def get_subject_speaker_id(*, case_id: str, session: Session) -> str | None:
    """Read this case's resolved target; unresolved cases wait for a selection."""
    case = session.get(CaseLog, case_id)
    if case is None:
        raise NotFound("The case does not exist")
    return case.target_speaker_id
