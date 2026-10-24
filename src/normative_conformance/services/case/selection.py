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
from normative_conformance.services.case.target import refresh_target
from normative_conformance.services.case.target import set_target_label
from normative_conformance.services.scheduler.request_assessment import request_assessment
from normative_conformance.services.scheduler.state import SchedulerState
from normative_conformance.timestamps import from_microseconds
from normative_conformance.timestamps import to_microseconds


def speaker_labels(*, case_id: str, session: Session) -> list[str]:
    """Use speech order, with stable tie breakers for overlapping observations."""
    return list(
        session.exec(
            select(Observation.speaker_id)
            .where(Observation.case_id == case_id)
            .order_by(
                col(Observation.start_at_us), col(Observation.end_at_us), col(Observation.sequence)
            )
        ).all()
    )


def to_record(*, case: CaseLog) -> CaseRecord:
    return CaseRecord(
        case_id=case.case_id,
        created_at=from_microseconds(value=case.created_at_us),
        target_speaker_order=case.target_speaker_order,
        target_speaker_id=case.target_speaker_id,
        target_speaker_manual=case.target_speaker_manual,
        target_revision=case.target_revision,
    )


def get_case(*, case_id: str, session: Session) -> CaseRecord:
    case = session.get(CaseLog, case_id)
    if case is None:
        raise NotFound("The case does not exist")
    return to_record(case=case)


def select_target(
    *,
    case_id: str,
    selection: TargetSelection,
    session: Session,
    now: Clock,
    scheduler: SchedulerState,
) -> CaseRecord:
    """Create/configure a case and request evaluation of any existing speech."""
    try:
        session.connection()
        case = session.get(CaseLog, case_id)
        if case is None:
            case = CaseLog(case_id=case_id, created_at_us=to_microseconds(value=now()))
            session.add(case)
        labels = speaker_labels(case_id=case_id, session=session)
        case.target_speaker_manual = selection.target_speaker_id is not None
        if case.target_speaker_manual:
            set_target_label(case=case, label=selection.target_speaker_id)
        else:
            case.target_speaker_order = selection.target_speaker_order
            refresh_target(case=case, labels=labels)
        record = to_record(case=case)
        session.commit()
    except SQLAlchemyError as error:
        session.rollback()
        raise StorageUnavailable("The target selection could not be stored") from error
    # Selecting a target wakes existing stored input.
    # Repeating the PUT also retries an enqueue failure after a successful commit.
    if labels and case.target_speaker_id is not None:
        request_assessment(case_id=case_id, scheduler=scheduler)
    return record
