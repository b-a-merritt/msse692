from typing import ClassVar

from sqlalchemy import ForeignKeyConstraint
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlmodel import Field
from sqlmodel import SQLModel


class Assessment(SQLModel, table=True):
    __tablename__: ClassVar[str] = "assessment"
    __table_args__ = (
        ForeignKeyConstraint(
            ["case_id", "target_revision"],
            ["target_assignment.case_id", "target_assignment.target_revision"],
        ),
        ForeignKeyConstraint(
            ["case_id", "through_sequence"], ["observation.case_id", "observation.sequence"]
        ),
    )

    assessment_id: int | None = Field(default=None, primary_key=True)
    case_id: str = Field(sa_type=Text)
    target_revision: int
    model_id: str = Field(sa_type=Text)
    prompt_version: str = Field(sa_type=Text)
    evaluated_at_us: int
    completed_at_us: int
    after_sequence: int
    through_sequence: int
    action: str | None = Field(default=None, sa_type=Text)
    action_confidence: float | None = None
    selection_threshold: float
    request_json: str = Field(sa_type=Text)


class AssessmentActionProbability(SQLModel, table=True):
    __tablename__: ClassVar[str] = "assessment_action_probability"

    assessment_id: int = Field(primary_key=True, foreign_key="assessment.assessment_id")
    action: str = Field(primary_key=True, sa_type=Text)
    probability: float


class Classification(SQLModel, table=True):
    __tablename__: ClassVar[str] = "classification"
    __table_args__ = (UniqueConstraint("assessment_id", "observation_key"),)

    classification_id: int | None = Field(default=None, primary_key=True)
    assessment_id: int = Field(foreign_key="assessment.assessment_id")
    observation_key: int = Field(foreign_key="observation.observation_key")
    primary_topic: str = Field(sa_type=Text)
    intensity: float | None


class ClassificationTopicScore(SQLModel, table=True):
    __tablename__: ClassVar[str] = "classification_topic_score"

    classification_id: int = Field(primary_key=True, foreign_key="classification.classification_id")
    topic: str = Field(primary_key=True, sa_type=Text)
    score: float


class ClassificationBehaviorScore(SQLModel, table=True):
    __tablename__: ClassVar[str] = "classification_behavior_score"

    classification_id: int = Field(primary_key=True, foreign_key="classification.classification_id")
    behavior: str = Field(primary_key=True, sa_type=Text)
    score: float
