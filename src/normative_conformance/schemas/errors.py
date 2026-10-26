from typing import Literal
from uuid import UUID

from normative_conformance.schemas.common import ContractModel

ErrorCode = Literal["NOT_FOUND", "OBSERVATION_EXISTS", "NOT_READY", "STORAGE_UNAVAILABLE"]


class ApiError(ContractModel):
    code: ErrorCode
    message: str
    request_id: UUID


class ErrorEnvelope(ContractModel):
    error: ApiError
