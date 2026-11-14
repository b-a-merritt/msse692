from sqlmodel import Session

from conversation_monitor.errors import NotFound
from conversation_monitor.models.case import ConversationCase
from conversation_monitor.schemas.case import CaseRecord
from conversation_monitor.services.case.records import to_record


def get_case(*, case_id: str, session: Session) -> CaseRecord:
    case = session.get(ConversationCase, case_id)
    if case is None:
        raise NotFound("The case does not exist")
    return to_record(case=case, session=session)
