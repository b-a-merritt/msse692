import logging
import time
from uuid import uuid4

from fastapi import Request
from fastapi import Response
from starlette.middleware.base import RequestResponseEndpoint

logger = logging.getLogger(__name__)


async def response_metadata(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    """Assign one server request ID, disable caching, and log each request."""
    request.state.request_id = uuid4()
    started = time.perf_counter()
    # An unhandled exception skips the response; ServerErrorMiddleware then returns 500.
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = str(request.state.request_id)
        response.headers["Cache-Control"] = "no-store"
        return response
    finally:
        logger.info(
            "Request completed",
            extra={
                "event": "http.request",
                "request_id": str(request.state.request_id),
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            },
        )
