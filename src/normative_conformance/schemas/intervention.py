from typing import Literal

from pydantic import AwareDatetime
from pydantic import Field

from normative_conformance.schemas.common import ContractModel
from normative_conformance.schemas.common import Identifier


class Intervention(ContractModel):
    intervention_id: int = Field(strict=True, ge=1)
    case_id: Identifier
    target_speaker_id: Identifier
    assessment_id: int = Field(strict=True, ge=1)
    message: str
    created_at: AwareDatetime
    status: Literal["pending", "sent"]
    sent_at: AwareDatetime | None
