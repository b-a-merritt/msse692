from sqlalchemy import Engine
from sqlalchemy import func
from sqlalchemy import or_
from sqlmodel import col
from sqlmodel import select

from normative_conformance.database import read_session
from normative_conformance.models.case import CaseLog
from normative_conformance.models.observation import Observation


def pending_cases(*, engine: Engine) -> list[str]:
    """Find resolved cases with unprocessed speech or a changed target."""
    with read_session(engine=engine) as session:
        return list(
            session.exec(
                select(CaseLog.case_id)
                .join(Observation, col(Observation.case_id) == CaseLog.case_id)
                .where(col(CaseLog.target_speaker_id).is_not(None))
                .group_by(col(CaseLog.case_id))
                .having(
                    or_(
                        func.max(Observation.sequence) > CaseLog.last_handled_sequence,
                        col(CaseLog.target_revision) != CaseLog.last_handled_target_revision,
                    )
                )
                .order_by(col(CaseLog.case_id))
            ).all()
        )
