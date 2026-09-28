from typing import ClassVar

from sqlalchemy import Text
from sqlmodel import Field
from sqlmodel import SQLModel


class Intervention(SQLModel, table=True):
    __tablename__: ClassVar[str] = "intervention"

    intervention_id: int | None = Field(default=None, primary_key=True)
    case_id: str = Field(foreign_key="case_log.case_id", sa_type=Text)
    message: str = Field(sa_type=Text)
    created_at_us: int
    sent_at_us: int | None = None


class InterventionSource(SQLModel, table=True):
    __tablename__: ClassVar[str] = "intervention_source"

    intervention_id: int = Field(foreign_key="intervention.intervention_id", primary_key=True)
    assessment_id: int = Field(
        foreign_key="assessment.assessment_id", primary_key=True, unique=True
    )
