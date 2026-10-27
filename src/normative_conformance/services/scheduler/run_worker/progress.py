"""How far the worker has handled each case for its current target."""

from sqlalchemy import ColumnElement
from sqlalchemy import case
from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance.models.case import ConversationCase
from normative_conformance.schemas.decision import DecisionSnapshot
from normative_conformance.services.case.target import current_assignment
from normative_conformance.services.case.target import current_revision


def handled_through() -> ColumnElement[int]:
    """Select the last sequence handled for a case's current target; a new target starts at 0."""
    return case(
        (
            col(ConversationCase.last_handled_target_revision)
            == current_revision(col(ConversationCase.case_id)),
            col(ConversationCase.last_handled_sequence),
        ),
        else_=0,
    )


def read_handled_through(*, case_id: str, session: Session) -> int:
    return session.exec(select(handled_through()).where(ConversationCase.case_id == case_id)).one()


def mark_handled(*, snapshot: DecisionSnapshot, session: Session) -> None:
    """Advance progress unless the target changed while the batch was being assessed."""
    conversation = session.get(ConversationCase, snapshot.case_id)
    current = current_assignment(case_id=snapshot.case_id, session=session)
    assert conversation is not None and current is not None
    if current.target_revision == snapshot.target_revision:
        conversation.last_handled_sequence = snapshot.through_sequence
        conversation.last_handled_target_revision = snapshot.target_revision
        session.add(conversation)
