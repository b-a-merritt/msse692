from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from normative_conformance.errors import StorageUnavailable
from normative_conformance.models.case import ConversationCase
from normative_conformance.schemas.case import CaseRecord
from normative_conformance.schemas.case import TargetSelection
from normative_conformance.schemas.internal import Clock
from normative_conformance.services.case.records import to_record
from normative_conformance.services.case.speaker_labels import speaker_labels
from normative_conformance.services.case.target import refresh_target
from normative_conformance.services.case.target import set_target_label
from normative_conformance.timestamps import to_microseconds


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
                case=case,
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
