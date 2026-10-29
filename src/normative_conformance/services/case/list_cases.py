from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance.models.case import ConversationCase
from normative_conformance.schemas.case import CaseRecord
from normative_conformance.services.case.records import to_record


def list_cases(*, session: Session) -> list[CaseRecord]:
    """List every case in case ID order."""
    cases = session.exec(select(ConversationCase).order_by(col(ConversationCase.case_id)))
    return [to_record(case=case, session=session) for case in cases]
