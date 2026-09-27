from datetime import datetime
from datetime import timezone

from pydantic import AwareDatetime
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator

from normative_conformance.schemas.common import ContractModel


class ObservationInput(ContractModel):
    case_id: str = Field(strict=True, min_length=1, pattern=r"^[^/]+$")
    observation_id: str = Field(strict=True, min_length=1, pattern=r"^[^/]+$")
    speaker_id: str = Field(strict=True, min_length=1, pattern=r"^[^/]+$")
    start_at: AwareDatetime
    end_at: AwareDatetime
    transcript: str = Field(strict=True, pattern=r"\S")
    signal_level_min: float = Field(strict=True, ge=-120, le=0)
    signal_level_avg: float = Field(strict=True, ge=-120, le=0)
    signal_level_max: float = Field(strict=True, ge=-120, le=0)

    @field_validator("start_at", "end_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_chunk(self) -> "ObservationInput":
        if self.end_at <= self.start_at:
            raise ValueError("End time must be after start time")
        if not self.signal_level_min <= self.signal_level_avg <= self.signal_level_max:
            raise ValueError("Signal levels must satisfy minimum <= average <= maximum")
        return self


class ObservationRecord(ObservationInput):
    received_at: AwareDatetime
    sequence: int = Field(strict=True, ge=1)
