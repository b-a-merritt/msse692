from collections.abc import AsyncIterator
from collections.abc import Iterator
from contextlib import asynccontextmanager
from contextlib import closing
from contextlib import contextmanager
from pathlib import Path
from threading import Thread
from typing import cast

from fastapi import FastAPI
from sqlalchemy import Engine

from normative_conformance.config import Settings
from normative_conformance.database import create_database_engine
from normative_conformance.database import initialize_database
from normative_conformance.queue import create_assessment_queue
from normative_conformance.services.scheduler.run_worker import run_worker
from normative_conformance.services.scheduler.state import SchedulerState


@contextmanager
def _scheduler_lifespan(
    *,
    app: FastAPI,
    engine: Engine,
    queue_path: Path,
) -> Iterator[None]:
    """Open the queue and keep it available until the worker has stopped."""
    with closing(create_assessment_queue(path=queue_path)) as queue:
        scheduler = SchedulerState(queue=queue)
        worker = Thread(
            target=run_worker,
            kwargs={"scheduler": scheduler, "engine": engine, "now": app.state.clock},
            name="assessment-worker",
        )

        app.state.assessment_queue = queue
        app.state.scheduler = scheduler
        app.state.assessment_worker = worker

        worker.start()
        try:
            yield
        finally:
            scheduler.stopped.set()
            worker.join()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize application resources and release them in dependency order."""
    settings = cast(Settings, app.state.settings)
    engine = create_database_engine(path=settings.app_db_path)

    try:
        initialize_database(engine=engine)
        app.state.engine = engine
        with _scheduler_lifespan(app=app, engine=engine, queue_path=settings.assessment_queue_path):
            yield
    finally:
        app.state.engine = None
        app.state.assessment_queue = None
        app.state.scheduler = None
        app.state.assessment_worker = None
        engine.dispose()
