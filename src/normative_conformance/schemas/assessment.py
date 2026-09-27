from dataclasses import dataclass
from typing import Annotated
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime
from pydantic import Field

from normative_conformance.schemas.common import ContractModel


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


@dataclass(frozen=True, kw_only=True)
class CaseSnapshot:
    evaluation_id: str
    case_id: str
    through_sequence: int
    evaluated_at_us: int
