import logging
from collections.abc import AsyncIterator
from collections.abc import Iterator
from contextlib import asynccontextmanager
from contextlib import contextmanager
from pathlib import Path
from threading import Event
from threading import Thread
from typing import cast

from fastapi import FastAPI
from sqlalchemy import Engine

from normative_conformance.config import Settings
from normative_conformance.database import create_database_engine
from normative_conformance.database import get_schema_revision
from normative_conformance.database import initialize_database
from normative_conformance.database import read_session
from normative_conformance.logging import start_logging
from normative_conformance.logging import stop_logging
from normative_conformance.schemas.model import ModelVersion
from normative_conformance.services.model.validate_models import validate_models
from normative_conformance.services.scheduler.run_worker.run_worker import run_worker

logger = logging.getLogger(__name__)


@contextmanager
def _worker_lifespan(
    *,
    app: FastAPI,
    engine: Engine,
    intervention_window_us: int,
    models: list[ModelVersion],
) -> Iterator[None]:
    """Keep the database available until the worker has stopped."""
    stopped = Event()
    worker = Thread(
        target=run_worker,
        kwargs={
            "stopped": stopped,
            "engine": engine,
            "now": app.state.clock,
            "intervention_window_us": intervention_window_us,
            "models": models,
        },
        name="assessment-worker",
    )

    app.state.worker_stopped = stopped
    app.state.assessment_worker = worker

    worker.start()
    try:
        yield
    finally:
        stopped.set()
        worker.join()


def _log_started(
    *,
    engine: Engine,
    settings: Settings,
    log_path: Path,
    models: list[ModelVersion],
) -> None:
    """Record the configuration that later decisions reference by model ID and version."""
    logger.info(
        "Application started",
        extra={
            "event": "app.started",
            "log_file": str(log_path),
            "schema_revision": get_schema_revision(engine=engine),
            "intervention_window_us": settings.intervention_window_us,
            "models": [
                {"model_id": model.model_id, "version": model.version, "type": model.type}
                for model in models
            ],
        },
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize application resources and release them in dependency order."""
    settings = cast(Settings, app.state.settings)
    log_path = start_logging(log_dir=settings.log_dir)
    stage = "database"

    try:
        engine = create_database_engine(path=settings.app_db_path)
        try:
            initialize_database(engine=engine)

            stage = "models"
            with read_session(engine=engine) as session:
                models = validate_models(session=session)
            app.state.engine = engine

            stage = "worker"
            with _worker_lifespan(
                app=app,
                engine=engine,
                intervention_window_us=settings.intervention_window_us,
                models=models,
            ):
                _log_started(
                    engine=engine,
                    settings=settings,
                    log_path=log_path,
                    models=models,
                )
                stage = "running"
                yield
        finally:
            app.state.engine = None
            app.state.worker_stopped = None
            app.state.assessment_worker = None
            engine.dispose()
    except Exception:
        if stage != "running":
            logger.exception(
                "Application startup failed",
                extra={"event": "app.start_failed", "stage": stage},
            )
        raise
    finally:
        if stage == "running":
            logger.info("Application stopped", extra={"event": "app.stopped"})
        stop_logging()
