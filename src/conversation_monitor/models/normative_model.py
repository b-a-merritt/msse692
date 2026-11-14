from typing import ClassVar

from sqlalchemy import Text
from sqlmodel import Field
from sqlmodel import SQLModel


class NormativeModel(SQLModel, table=True):
    __tablename__: ClassVar[str] = "normative_model"

    normative_model_id: int | None = Field(default=None, primary_key=True)
    discovered_at_us: int


class NormativeModelTopic(SQLModel, table=True):
    """A topic that came before undesired behavior in every conversation discovered from."""

    __tablename__: ClassVar[str] = "normative_model_topic"

    normative_model_id: int = Field(
        primary_key=True, foreign_key="normative_model.normative_model_id"
    )
    topic: str = Field(primary_key=True, sa_type=Text)


class NormativeModelAssessment(SQLModel, table=True):
    __tablename__: ClassVar[str] = "normative_model_assessment"

    normative_model_id: int = Field(
        primary_key=True, foreign_key="normative_model.normative_model_id"
    )
    assessment_id: int = Field(primary_key=True, foreign_key="assessment.assessment_id")
