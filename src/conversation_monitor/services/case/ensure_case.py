from sqlmodel import Session

from conversation_monitor.models.case import ConversationCase
from conversation_monitor.schemas.case import CaseRecord
from conversation_monitor.services.case.records import to_record


def ensure_case(*, case_id: str, created_at_us: int, session: Session) -> CaseRecord:
    """Return the case, creating it without committing if it does not exist."""
    case = session.get(ConversationCase, case_id)
    if case is None:
        case = ConversationCase(case_id=case_id, created_at_us=created_at_us)
        session.add(case)
        session.flush()
    return to_record(case=case, session=session)
