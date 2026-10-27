from sqlalchemy import Engine
from sqlalchemy import and_
from sqlalchemy import func
from sqlalchemy import or_
from sqlmodel import col
from sqlmodel import select

from normative_conformance.database import read_session
from normative_conformance.models.case import CaseLog
from normative_conformance.models.case import TargetAssignment
from normative_conformance.models.observation import Observation
from normative_conformance.services.case.target import current_revision


def pending_cases(*, engine: Engine) -> list[str]:
    """Find resolved cases with unprocessed speech or a changed target."""
    last_sequence = (
        select(func.max(Observation.sequence))
        .where(Observation.case_id == CaseLog.case_id)
        .scalar_subquery()
    )
    with read_session(engine=engine) as session:
        return list(
            session.exec(
                select(CaseLog.case_id)
                .join(
                    TargetAssignment,
                    and_(
                        col(TargetAssignment.case_id) == CaseLog.case_id,
                        col(TargetAssignment.target_revision)
                        == current_revision(col(CaseLog.case_id)),
                    ),
                )
                .where(
                    col(TargetAssignment.speaker_id).is_not(None),
                    or_(
                        last_sequence > CaseLog.last_handled_sequence,
                        (
                            col(TargetAssignment.target_revision)
                            != CaseLog.last_handled_target_revision
                        )
                        & last_sequence.is_not(None),
                    ),
                )
                .order_by(col(CaseLog.case_id))
            ).all()
        )
