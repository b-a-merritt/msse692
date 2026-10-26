from typing import ClassVar

from sqlalchemy import Index
from sqlalchemy import Text
from sqlmodel import Field
from sqlmodel import SQLModel


class SpeakerRevision(SQLModel, table=True):
    __tablename__: ClassVar[str] = "speaker_revision"
    __table_args__ = (Index("speaker_revision_case", "case_id", "revision_id"),)

    revision_id: int | None = Field(default=None, primary_key=True)
    case_id: str = Field(foreign_key="case_log.case_id", sa_type=Text)
    received_at_us: int
    replaced_observation_ids_json: str = Field(sa_type=Text)
    observations_json: str = Field(sa_type=Text)
