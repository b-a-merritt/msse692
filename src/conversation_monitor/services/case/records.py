from sqlmodel import Session

from conversation_monitor.models.case import ConversationCase
from conversation_monitor.schemas.case import CaseRecord
from conversation_monitor.services.case.target import current_assignment
from conversation_monitor.timestamps import from_microseconds


def to_record(*, case: ConversationCase, session: Session) -> CaseRecord:
    assignment = current_assignment(case_id=case.case_id, session=session)
    return CaseRecord(
        case_id=case.case_id,
        created_at=from_microseconds(value=case.created_at_us),
        target_speaker_order=case.target_speaker_order,
        target_speaker_id=assignment.speaker_id if assignment is not None else None,
        target_revision=assignment.target_revision if assignment is not None else 0,
    )
