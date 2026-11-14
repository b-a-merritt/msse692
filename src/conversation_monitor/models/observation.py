from typing import ClassVar

from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlmodel import Field
from sqlmodel import SQLModel


class Observation(SQLModel, table=True):
    """Ingested speech has a sequence; speech from a speaker revision has a revision instead."""

    __tablename__: ClassVar[str] = "observation"
    __table_args__ = (
        UniqueConstraint("case_id", "sequence"),
        UniqueConstraint("speaker_revision_id", "observation_id"),
    )

    observation_key: int | None = Field(default=None, primary_key=True)
    case_id: str = Field(foreign_key="conversation_case.case_id", sa_type=Text)
    observation_id: str = Field(sa_type=Text)
    speaker_revision_id: int | None = Field(
        default=None, foreign_key="speaker_revision.speaker_revision_id"
    )
    sequence: int | None = None
    received_at_us: int | None = None
    speaker_id: str = Field(sa_type=Text)
    start_at_us: int
    end_at_us: int
    transcript: str = Field(sa_type=Text)
    signal_level_min: float
    signal_level_avg: float
    signal_level_max: float
