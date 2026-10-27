from typing import ClassVar

from sqlalchemy import Text
from sqlmodel import Field
from sqlmodel import SQLModel


class SpeakerRevision(SQLModel, table=True):
    __tablename__: ClassVar[str] = "speaker_revision"

    speaker_revision_id: int | None = Field(default=None, primary_key=True)
    case_id: str = Field(foreign_key="case_log.case_id", sa_type=Text)
    received_at_us: int


class ReplacedObservation(SQLModel, table=True):
    __tablename__: ClassVar[str] = "replaced_observation"

    speaker_revision_id: int = Field(
        primary_key=True, foreign_key="speaker_revision.speaker_revision_id"
    )
    observation_key: int = Field(primary_key=True, foreign_key="observation.observation_key")
