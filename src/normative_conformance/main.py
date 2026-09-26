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


async def response_metadata(request: Request, call_next: RequestResponseEndpoint) -> Response:
    """Assign one server request ID and disable caching for each response."""
    request.state.request_id = uuid4()
    response = await call_next(request)
    response.headers["X-Request-ID"] = str(request.state.request_id)
    response.headers["Cache-Control"] = "no-store"
    return response


def create_app(*, settings: Settings | None = None, now: Clock = utc_now) -> FastAPI:
    settings = settings if settings is not None else get_settings()

    application = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
    application.state.settings = settings
    application.state.clock = now

    application.middleware("http")(response_metadata)
    register_error_handlers(application=application)

    application.include_router(router)

    return application


app = create_app()
