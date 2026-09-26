from typing import Literal

from pydantic import AwareDatetime
from pydantic import Field

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


class ObservationRecord(ObservationInput):
    received_at: AwareDatetime
    sequence: int = Field(strict=True, ge=1)


class ObservationAccepted(ContractModel):
    observation: ObservationRecord
    assessment_requested: Literal[True]


class ObservationList(ContractModel):
    items: list[ObservationRecord]
