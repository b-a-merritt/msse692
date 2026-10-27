from sqlmodel import Session

from normative_conformance.models.case import ConversationCase
from normative_conformance.schemas.case import CaseRecord
from normative_conformance.services.case.target import current_assignment
from normative_conformance.timestamps import from_microseconds


def to_record(*, case: ConversationCase, session: Session) -> CaseRecord:
    assignment = current_assignment(case_id=case.case_id, session=session)
    return CaseRecord(
        case_id=case.case_id,
        created_at=from_microseconds(value=case.created_at_us),
        target_speaker_order=case.target_speaker_order,
        target_speaker_id=assignment.speaker_id if assignment is not None else None,
        target_revision=assignment.target_revision if assignment is not None else 0,
    )
