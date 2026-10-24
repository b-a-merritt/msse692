from typing import ClassVar

from sqlalchemy import Text
from sqlmodel import Field
from sqlmodel import SQLModel


class CaseLog(SQLModel, table=True):
    __tablename__: ClassVar[str] = "case_log"

    case_id: str = Field(primary_key=True, sa_type=Text)
    created_at_us: int
    target_speaker_order: int | None = None
    target_speaker_id: str | None = Field(default=None, sa_type=Text)
    target_speaker_manual: bool = False
    target_revision: int = 0
