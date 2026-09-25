from typing import ClassVar

from sqlalchemy import ForeignKeyConstraint
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlmodel import Field
from sqlmodel import SQLModel


class Assessment(SQLModel, table=True):
    __tablename__: ClassVar[str] = "assessment"
    __table_args__ = (
        UniqueConstraint("evaluation_id", "model_id", "model_version"),
        ForeignKeyConstraint(
            ["case_id", "through_sequence"], ["observation.case_id", "observation.sequence"]
        ),
        ForeignKeyConstraint(
            ["model_id", "model_version"],
            ["normative_model_version.model_id", "normative_model_version.version"],
        ),
    )

    assessment_id: int | None = Field(default=None, primary_key=True)
    evaluation_id: str = Field(sa_type=Text)
    case_id: str = Field(sa_type=Text)
    model_id: str = Field(sa_type=Text)
    model_version: str = Field(sa_type=Text)
    evaluated_at_us: int
    through_sequence: int
    status: str = Field(sa_type=Text)
    explanation_json: str = Field(sa_type=Text)
    next_due_at_us: int | None = None
