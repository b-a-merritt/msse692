from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from conversation_monitor.errors import StorageUnavailable
from conversation_monitor.models.case import ConversationCase
from conversation_monitor.schemas.case import CaseRecord
from conversation_monitor.schemas.case import TargetSelection
from conversation_monitor.schemas.internal import Clock
from conversation_monitor.services.case.records import to_record
from conversation_monitor.services.case.speaker_labels import speaker_labels
from conversation_monitor.services.case.target import refresh_target
from conversation_monitor.services.case.target import set_target_label
from conversation_monitor.timestamps import to_microseconds


def select_target(
    *,
    case_id: str,
    selection: TargetSelection,
    session: Session,
    now: Clock,
) -> CaseRecord:
    """Persist the target selection for a case."""
    try:
        session.connection()
        selected_at_us = to_microseconds(value=now())
        case = session.get(ConversationCase, case_id)
        if case is None:
            case = ConversationCase(case_id=case_id, created_at_us=selected_at_us)
            session.add(case)
        case.target_speaker_order = selection.target_speaker_order
        if selection.target_speaker_id is not None:
            set_target_label(
                case_id=case_id,
                label=selection.target_speaker_id,
                session=session,
                assigned_at_us=selected_at_us,
            )
        else:
            refresh_target(
                case_id=case_id,
                target_speaker_order=selection.target_speaker_order,
                labels=speaker_labels(case_id=case_id, session=session),
                session=session,
                assigned_at_us=selected_at_us,
            )
        record = to_record(case=case, session=session)
        session.commit()
    except SQLAlchemyError as error:
        session.rollback()
        raise StorageUnavailable("The target selection could not be stored") from error
    return record
