from fastapi import FastAPI

from conversation_monitor.body_limit import body_limit
from conversation_monitor.config import Settings
from conversation_monitor.config import get_settings
from conversation_monitor.lifespan import lifespan
from conversation_monitor.middleware import response_metadata
from conversation_monitor.routes import router
from conversation_monitor.routes.errors import register_error_handlers
from conversation_monitor.schemas.internal import Clock
from conversation_monitor.timestamps import utc_now


def create_app(
    *,
    settings: Settings | None = None,
    now: Clock = utc_now,
) -> FastAPI:
    settings = settings if settings is not None else get_settings()

    application = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
    application.state.settings = settings
    application.state.clock = now
    application.state.active_captures = 0

    # The last added runs first, so a rejected body still gets a request ID and a log record.
    application.add_middleware(body_limit)
    application.middleware("http")(response_metadata)
    register_error_handlers(application=application)

    application.include_router(router)

    return application


app = create_app()
