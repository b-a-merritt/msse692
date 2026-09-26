from typing import Any
from typing import Literal
from typing import cast
from uuid import UUID

from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse

from normative_conformance.errors import EnqueueFailed
from normative_conformance.errors import NotFound
from normative_conformance.errors import NotReady
from normative_conformance.errors import ObservationExists
from normative_conformance.errors import StorageUnavailable
from normative_conformance.schemas.errors import ApiError
from normative_conformance.schemas.errors import ErrorEnvelope
from normative_conformance.schemas.observation import ObservationRecord

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    503: {"model": ErrorEnvelope, "description": "Service unavailable"}
}

# Lookup is by exact type, so subclasses can fall through
_TRANSLATIONS: dict[
    type[Exception],
    tuple[
        int,
        Literal[
            "NOT_FOUND", "OBSERVATION_EXISTS", "NOT_READY", "STORAGE_UNAVAILABLE", "ENQUEUE_FAILED"
        ],
    ],
] = {
    NotFound: (404, "NOT_FOUND"),
    ObservationExists: (409, "OBSERVATION_EXISTS"),
    NotReady: (503, "NOT_READY"),
    StorageUnavailable: (503, "STORAGE_UNAVAILABLE"),
    EnqueueFailed: (503, "ENQUEUE_FAILED"),
}


def _envelope(
    *,
    request: Request,
    status: int,
    code: Literal[
        "NOT_FOUND", "OBSERVATION_EXISTS", "NOT_READY", "STORAGE_UNAVAILABLE", "ENQUEUE_FAILED"
    ],
    message: str,
    committed_observation: ObservationRecord | None = None,
) -> JSONResponse:
    """Render one error body carrying the request ID the middleware assigned."""
    body = ErrorEnvelope(
        error=ApiError(
            code=code,
            message=message,
            request_id=cast(UUID, request.state.request_id),
            committed_observation=committed_observation,
        )
    )
    return JSONResponse(status_code=status, content=body.model_dump(mode="json", exclude_none=True))


async def unimplemented_operation(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Keep placeholder operations explicitly unavailable until implemented."""
    return _envelope(
        request=request,
        status=503,
        code="NOT_READY",
        message="This operation is not implemented yet",
    )


async def service_error(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Translate domain failures at the HTTP boundary, where request IDs belong."""
    status, code = _TRANSLATIONS[type(exc)]
    return _envelope(
        request=request,
        status=status,
        code=code,
        message=str(exc),
        committed_observation=exc.committed_observation if isinstance(exc, EnqueueFailed) else None,
    )


def register_error_handlers(
    *,
    application: FastAPI,
) -> None:
    """Attach the placeholder and domain failure handlers to the application."""
    application.add_exception_handler(NotImplementedError, unimplemented_operation)
    for error in _TRANSLATIONS:
        application.add_exception_handler(error, service_error)
