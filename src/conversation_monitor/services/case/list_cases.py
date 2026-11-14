from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from conversation_monitor.models.case import ConversationCase
from conversation_monitor.schemas.case import CaseRecord
from conversation_monitor.services.case.records import to_record


def list_cases(*, session: Session) -> list[CaseRecord]:
    """List every case in case ID order."""
    cases = session.exec(select(ConversationCase).order_by(col(ConversationCase.case_id)))
    return [to_record(case=case, session=session) for case in cases]
