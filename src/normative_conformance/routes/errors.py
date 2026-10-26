import logging
from typing import Any
from typing import cast
from uuid import UUID

from fastapi import FastAPI
from fastapi import Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.responses import Response

from normative_conformance.errors import NotFound
from normative_conformance.errors import NotReady
from normative_conformance.errors import ObservationExists
from normative_conformance.errors import StorageUnavailable
from normative_conformance.schemas.errors import ApiError
from normative_conformance.schemas.errors import ErrorCode
from normative_conformance.schemas.errors import ErrorEnvelope

logger = logging.getLogger(__name__)

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    503: {"model": ErrorEnvelope, "description": "Service unavailable"}
}

# Lookup is by exact type, so subclasses can fall through
_TRANSLATIONS: dict[
    type[Exception],
    tuple[int, ErrorCode],
] = {
    NotFound: (404, "NOT_FOUND"),
    ObservationExists: (409, "OBSERVATION_EXISTS"),
    NotReady: (503, "NOT_READY"),
    StorageUnavailable: (503, "STORAGE_UNAVAILABLE"),
}


def _envelope(
    *,
    request: Request,
    status: int,
    code: ErrorCode,
    message: str,
) -> JSONResponse:
    """Render one error body carrying the request ID the middleware assigned."""
    body = ErrorEnvelope(
        error=ApiError(
            code=code,
            message=message,
            request_id=cast(UUID, request.state.request_id),
        )
    )
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"))


async def service_error(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Translate domain failures at the HTTP boundary, where request IDs belong."""
    status, code = _TRANSLATIONS[type(exc)]
    route = request.scope.get("route")
    logger.log(
        logging.WARNING if status < 500 else logging.ERROR,
        "Request rejected",
        exc_info=exc if status >= 500 else None,
        extra={
            "event": "http.rejected",
            "request_id": str(request.state.request_id),
            "status": status,
            "code": code,
            "method": request.method,
            "route": getattr(route, "path", None),
            "path_params": dict(request.path_params),
        },
    )
    return _envelope(
        request=request,
        status=status,
        code=code,
        message=str(exc),
    )


async def validation_error(request: Request, exc: Exception) -> Response:
    """Log which fields were rejected, never their values, then use FastAPI's response."""
    assert isinstance(exc, RequestValidationError)
    route = request.scope.get("route")
    logger.warning(
        "Request rejected",
        extra={
            "event": "http.rejected",
            "request_id": str(request.state.request_id),
            "status": 422,
            "method": request.method,
            "route": getattr(route, "path", None),
            "fields": [
                {"loc": list(error["loc"]), "type": error["type"]} for error in exc.errors()
            ],
        },
    )
    return await request_validation_exception_handler(request, exc)


def register_error_handlers(
    *,
    application: FastAPI,
) -> None:
    """Attach the validation and domain failure handlers to the application."""
    application.add_exception_handler(RequestValidationError, validation_error)
    for error in _TRANSLATIONS:
        application.add_exception_handler(error, service_error)
