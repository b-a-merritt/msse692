from pydantic import AwareDatetime
from pydantic import Field
from pydantic import model_validator

from normative_conformance.schemas.common import ContractModel


class TargetSelection(ContractModel):
    target_speaker_order: int | None = Field(default=None, strict=True, ge=1, le=2)
    target_speaker_id: str | None = Field(default=None, strict=True, pattern=r"^[^/]+$")

    @model_validator(mode="after")
    def validate_selection(self) -> "TargetSelection":
        if (self.target_speaker_order is None) == (self.target_speaker_id is None):
            raise ValueError("Supply either target_speaker_order or target_speaker_id")
        if self.target_speaker_id is not None and (
            not self.target_speaker_id.strip() or self.target_speaker_id == "PENDING"
        ):
            raise ValueError("The target must be a resolved speaker label")
        return self


class CaseRecord(ContractModel):
    case_id: str
    created_at: AwareDatetime
    target_speaker_order: int | None
    target_speaker_id: str | None
    target_revision: int
