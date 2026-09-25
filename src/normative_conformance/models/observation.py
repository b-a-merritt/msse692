from typing import ClassVar

from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlmodel import Field
from sqlmodel import SQLModel


class Observation(SQLModel, table=True):
    __tablename__: ClassVar[str] = "observation"
    __table_args__ = (UniqueConstraint("case_id", "sequence"),)

    case_id: str = Field(primary_key=True, foreign_key="case_log.case_id", sa_type=Text)
    observation_id: str = Field(primary_key=True, sa_type=Text)
    sequence: int
    received_at_us: int
    speaker_id: str = Field(sa_type=Text)
    start_at_us: int
    end_at_us: int
    transcript: str = Field(sa_type=Text)
    signal_level_min: float
    signal_level_avg: float
    signal_level_max: float
