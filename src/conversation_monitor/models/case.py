from typing import ClassVar

from sqlalchemy import Text
from sqlmodel import Field
from sqlmodel import SQLModel


class ConversationCase(SQLModel, table=True):
    __tablename__: ClassVar[str] = "conversation_case"

    case_id: str = Field(primary_key=True, sa_type=Text)
    created_at_us: int
    target_speaker_order: int | None = None
    last_handled_sequence: int = 0
    last_handled_target_revision: int = 0


class TargetAssignment(SQLModel, table=True):
    __tablename__: ClassVar[str] = "target_assignment"

    case_id: str = Field(primary_key=True, foreign_key="conversation_case.case_id", sa_type=Text)
    target_revision: int = Field(primary_key=True)
    assigned_at_us: int
    speaker_id: str | None = Field(default=None, sa_type=Text)
