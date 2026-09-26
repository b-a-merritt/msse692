from typing import Literal
from uuid import UUID

from normative_conformance.schemas.common import ContractModel
from normative_conformance.schemas.observation import ObservationRecord


class ApiError(ContractModel):
    code: Literal[
        "NOT_FOUND", "OBSERVATION_EXISTS", "NOT_READY", "STORAGE_UNAVAILABLE", "ENQUEUE_FAILED"
    ]
    message: str
    request_id: UUID
    committed_observation: ObservationRecord | None = None


class ErrorEnvelope(ContractModel):
    error: ApiError
