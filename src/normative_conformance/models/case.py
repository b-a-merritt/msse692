from typing import ClassVar

from sqlalchemy import Text
from sqlmodel import Field
from sqlmodel import SQLModel


class ExperimentConfig(SQLModel, table=True):
    __tablename__: ClassVar[str] = "experiment_config"

    experiment_id: int = Field(default=1, primary_key=True)
    subject_speaker_id: str = Field(sa_type=Text)
    created_at_us: int


class CaseLog(SQLModel, table=True):
    __tablename__: ClassVar[str] = "case_log"

    case_id: str = Field(primary_key=True, sa_type=Text)
    created_at_us: int
