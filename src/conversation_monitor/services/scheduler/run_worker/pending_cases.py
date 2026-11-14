from sqlalchemy import Engine
from sqlalchemy import and_
from sqlalchemy import func
from sqlmodel import col
from sqlmodel import select

from conversation_monitor.database import read_session
from conversation_monitor.models.case import ConversationCase
from conversation_monitor.models.case import TargetAssignment
from conversation_monitor.models.observation import Observation
from conversation_monitor.services.case.progress import handled_through
from conversation_monitor.services.case.target import current_revision


def pending_cases(*, engine: Engine) -> list[str]:
    """Find cases with a resolved target and speech it has not handled."""
    last_sequence = (
        select(func.max(Observation.sequence))
        .where(Observation.case_id == ConversationCase.case_id)
        .scalar_subquery()
    )
    with read_session(engine=engine) as session:
        return list(
            session.exec(
                select(ConversationCase.case_id)
                .join(
                    TargetAssignment,
                    and_(
                        col(TargetAssignment.case_id) == ConversationCase.case_id,
                        col(TargetAssignment.target_revision)
                        == current_revision(col(ConversationCase.case_id)),
                    ),
                )
                .where(
                    col(TargetAssignment.speaker_id).is_not(None),
                    last_sequence > handled_through(),
                )
                .order_by(col(ConversationCase.case_id))
            ).all()
        )
