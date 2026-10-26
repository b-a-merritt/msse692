from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime
from pydantic import Field

from normative_conformance.schemas.common import ContractModel
from normative_conformance.schemas.common import Identifier

AssessmentStatus = Literal["conformant", "non-conformant", "pending", "conflicted"]


class Extent(ContractModel):
    through_sequence: int = Field(strict=True, ge=1)
    observation_count: int = Field(strict=True, ge=1)
    observation_ids: list[Identifier] = Field(min_length=1)


class RuleResult(ContractModel):
    rule_id: Identifier
    outcome: Literal["satisfied", "not_satisfied", "pending"]
    reason: str
    observation_ids: list[Identifier]
    deadline_at: AwareDatetime | None


class Explanation(ContractModel):
    reason_code: Identifier
    summary: str
    rules: list[RuleResult] = Field(min_length=1)


class Assessment(ContractModel):
    assessment_id: int = Field(strict=True, ge=1)
    resolves_assessment_id: int | None = Field(default=None, strict=True, ge=1)
    evaluation_id: UUID
    case_id: Identifier
    subject_speaker_id: Identifier
    model_id: Identifier
    model_version: str = Field(strict=True, min_length=1)
    evaluated_at: AwareDatetime
    status: AssessmentStatus
    extent: Extent
    explanation: Explanation
    next_due_at: AwareDatetime | None


@dataclass(frozen=True, kw_only=True)
class CaseSnapshot:
    evaluation_id: str
    case_id: str
    through_sequence: int
    evaluated_at_us: int
