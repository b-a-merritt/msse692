from typing import Literal

from pydantic import AwareDatetime
from pydantic import Field

from normative_conformance.schemas.common import ContractModel


class Intervention(ContractModel):
    intervention_id: int = Field(strict=True, ge=1)
    case_id: str = Field(strict=True, min_length=1, pattern=r"^[^/]+$")
    subject_speaker_id: str = Field(strict=True, min_length=1, pattern=r"^[^/]+$")
    assessment_id: int = Field(strict=True, ge=1)
    message: str
    created_at: AwareDatetime
    status: Literal["pending", "sent"]
    sent_at: AwareDatetime | None


class InterventionList(ContractModel):
    items: list[Intervention]
