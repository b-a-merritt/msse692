from typing import Literal
from uuid import UUID

from normative_conformance.schemas.common import ContractModel


class ApiError(ContractModel):
    code: Literal["NOT_FOUND", "OBSERVATION_EXISTS", "NOT_READY", "STORAGE_UNAVAILABLE"]
    message: str
    request_id: UUID


class ErrorEnvelope(ContractModel):
    error: ApiError
