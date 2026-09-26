from dataclasses import dataclass
from datetime import datetime
from typing import Annotated
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime
from pydantic import Field

from normative_conformance.schemas.common import ContractModel
from normative_conformance.schemas.observation import ObservationRecord


class Extent(ContractModel):
    through_sequence: int = Field(strict=True, ge=1)
    observation_count: int = Field(strict=True, ge=1)
    observation_ids: list[Annotated[str, Field(strict=True, min_length=1, pattern=r"^[^/]+$")]] = (
        Field(min_length=1)
    )


class RuleResult(ContractModel):
    rule_id: str = Field(strict=True, min_length=1, pattern=r"^[^/]+$")
    outcome: Literal["satisfied", "not_satisfied", "pending"]
    reason: str
    observation_ids: list[Annotated[str, Field(strict=True, min_length=1, pattern=r"^[^/]+$")]]
    deadline_at: AwareDatetime | None


class Explanation(ContractModel):
    reason_code: str = Field(strict=True, min_length=1, pattern=r"^[^/]+$")
    summary: str
    rules: list[RuleResult] = Field(min_length=1)


class Assessment(ContractModel):
    assessment_id: int = Field(strict=True, ge=1)
    resolves_assessment_id: int | None = Field(default=None, strict=True, ge=1)
    evaluation_id: UUID
    case_id: str = Field(strict=True, min_length=1, pattern=r"^[^/]+$")
    subject_speaker_id: str = Field(strict=True, min_length=1, pattern=r"^[^/]+$")
    model_id: str = Field(strict=True, min_length=1, pattern=r"^[^/]+$")
    model_version: str = Field(strict=True, min_length=1)
    evaluated_at: AwareDatetime
    status: Literal["conformant", "non-conformant", "pending", "conflicted"]
    extent: Extent
    explanation: Explanation
    next_due_at: AwareDatetime | None


class AssessmentList(ContractModel):
    items: list[Assessment]


@dataclass(frozen=True, kw_only=True)
class CaseSnapshot:
    evaluation_id: UUID
    case_id: str
    subject_speaker_id: str
    evaluated_at: datetime
    through_sequence: int
    observations: tuple[ObservationRecord, ...]


@dataclass(frozen=True, kw_only=True)
class ModelEvaluation:
    model_id: str
    model_version: str
    status: Literal["conformant", "non-conformant", "pending", "conflicted"]
    explanation: Explanation
    next_due_at: datetime | None
