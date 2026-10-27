from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance.errors import NotFound
from normative_conformance.errors import StorageUnavailable
from normative_conformance.models.case import CaseLog
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.case import CaseRecord
from normative_conformance.schemas.case import TargetSelection
from normative_conformance.schemas.internal import Clock
from normative_conformance.services.case.target import current_assignment
from normative_conformance.services.case.target import refresh_target
from normative_conformance.services.case.target import set_target_label
from normative_conformance.timestamps import from_microseconds
from normative_conformance.timestamps import to_microseconds


def speaker_labels(*, case_id: str, session: Session) -> list[str]:
    """Use speech order, with stable tie breakers for overlapping observations."""
    return list(
        session.exec(
            select(Observation.speaker_id)
            .where(Observation.case_id == case_id, col(Observation.sequence).is_not(None))
            .order_by(
                col(Observation.start_at_us), col(Observation.end_at_us), col(Observation.sequence)
            )
        ).all()
    )


def to_record(*, case: CaseLog, session: Session) -> CaseRecord:
    assignment = current_assignment(case_id=case.case_id, session=session)
    target_speaker_id = assignment.speaker_id if assignment is not None else None
    return CaseRecord(
        case_id=case.case_id,
        created_at=from_microseconds(value=case.created_at_us),
        target_speaker_order=case.target_speaker_order,
        target_speaker_id=target_speaker_id,
        # A speaker chosen by label is the only assignment without a speaking order.
        target_speaker_manual=case.target_speaker_order is None and target_speaker_id is not None,
        target_revision=assignment.target_revision if assignment is not None else 0,
    )


def get_case(*, case_id: str, session: Session) -> CaseRecord:
    case = session.get(CaseLog, case_id)
    if case is None:
        raise NotFound("The case does not exist")
    return to_record(case=case, session=session)


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
        case = session.get(CaseLog, case_id)
        if case is None:
            case = CaseLog(case_id=case_id, created_at_us=selected_at_us)
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
