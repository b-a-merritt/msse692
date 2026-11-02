from typing import Literal
from uuid import UUID

from normative_conformance.schemas.common import ContractModel

ErrorCode = Literal[
    "FOREIGN_REQUEST",
    "NOT_FOUND",
    "OBSERVATION_EXISTS",
    "BODY_TOO_LARGE",
    "NOT_READY",
    "STORAGE_UNAVAILABLE",
]


class ApiError(ContractModel):
    code: ErrorCode
    message: str
    request_id: UUID


class ErrorEnvelope(ContractModel):
    error: ApiError
