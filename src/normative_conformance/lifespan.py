from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextlib import closing
from typing import cast

from fastapi import FastAPI

from normative_conformance.config import Settings
from normative_conformance.database import create_database_engine
from normative_conformance.database import initialize_database
from normative_conformance.queue import create_assessment_queue


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Own the application database and assessment queue for one process."""
    settings = cast(Settings, app.state.settings)
    engine = create_database_engine(path=settings.app_db_path)
    try:
        initialize_database(engine=engine)
        with closing(create_assessment_queue(path=settings.assessment_queue_path)) as queue:
            app.state.engine = engine
            app.state.assessment_queue = queue
            yield
    finally:
        app.state.engine = None
        app.state.assessment_queue = None
        engine.dispose()
