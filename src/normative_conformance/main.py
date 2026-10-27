from fastapi import FastAPI

from normative_conformance.config import Settings
from normative_conformance.config import get_settings
from normative_conformance.lifespan import lifespan
from normative_conformance.middleware import response_metadata
from normative_conformance.routes import router
from normative_conformance.routes.errors import register_error_handlers
from normative_conformance.schemas.internal import Clock
from normative_conformance.timestamps import utc_now


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
