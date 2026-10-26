from sqlalchemy import Engine
from sqlalchemy import func
from sqlalchemy import or_
from sqlmodel import col
from sqlmodel import select

from normative_conformance.database import read_session
from normative_conformance.models.assessment import Assessment
from normative_conformance.models.case import CaseLog
from normative_conformance.models.observation import Observation


def pending_cases(*, engine: Engine, now_us: int) -> list[str]:
    """Find resolved cases with unprocessed speech, a changed target, or a due repair deadline."""
    last_sequence = (
        select(func.max(Observation.sequence))
        .where(Observation.case_id == CaseLog.case_id)
        .scalar_subquery()
    )
    resolved = select(Assessment.resolves_assessment_id).where(
        col(Assessment.resolves_assessment_id).is_not(None)
    )
    repair_due = (
        select(Assessment.assessment_id)
        .where(
            Assessment.case_id == CaseLog.case_id,
            Assessment.target_revision == CaseLog.target_revision,
            Assessment.subject_speaker_id == CaseLog.target_speaker_id,
            Assessment.status == "pending",
            col(Assessment.next_due_at_us) <= now_us,
            col(Assessment.assessment_id).not_in(resolved),
        )
        .exists()
    )
    with read_session(engine=engine) as session:
        return list(
            session.exec(
                select(CaseLog.case_id)
                .where(
                    col(CaseLog.target_speaker_id).is_not(None),
                    or_(
                        last_sequence > CaseLog.last_handled_sequence,
                        (col(CaseLog.target_revision) != CaseLog.last_handled_target_revision)
                        & last_sequence.is_not(None),
                        repair_due,
                    ),
                )
                .order_by(col(CaseLog.case_id))
            ).all()
        )
