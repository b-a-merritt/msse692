from sqlmodel import Session

from normative_conformance.errors import NotFound
from normative_conformance.models.case import ConversationCase
from normative_conformance.schemas.case import CaseRecord
from normative_conformance.services.case.records import to_record


def get_case(*, case_id: str, session: Session) -> CaseRecord:
    case = session.get(ConversationCase, case_id)
    if case is None:
        raise NotFound("The case does not exist")
    return to_record(case=case, session=session)
