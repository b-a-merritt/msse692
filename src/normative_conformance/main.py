import logging
import time
from uuid import uuid4

from fastapi import FastAPI
from fastapi import Request
from fastapi import Response
from starlette.middleware.base import RequestResponseEndpoint

from normative_conformance.config import Settings
from normative_conformance.config import get_settings
from normative_conformance.config import utc_now
from normative_conformance.lifespan import lifespan
from normative_conformance.routes import router
from normative_conformance.routes.errors import register_error_handlers
from normative_conformance.schemas.internal import Clock

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


def create_app(
    *,
    settings: Settings | None = None,
    now: Clock = utc_now,
) -> FastAPI:
    settings = settings if settings is not None else get_settings()

    application = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
    application.state.settings = settings
    application.state.clock = now

    application.middleware("http")(response_metadata)
    register_error_handlers(application=application)

    application.include_router(router)

    return application


app = create_app()
