import logging
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
from normative_conformance.database import get_schema_revision
from normative_conformance.database import initialize_database
from normative_conformance.database import initialize_experiment_config
from normative_conformance.database import read_session
from normative_conformance.logging import start_logging
from normative_conformance.logging import stop_logging
from normative_conformance.queue import create_assessment_queue
from normative_conformance.services.model.get_subject_speaker_id import get_subject_speaker_id
from normative_conformance.services.model.list_models import list_models
from normative_conformance.services.scheduler.run_worker import run_worker
from normative_conformance.services.scheduler.state import SchedulerState

logger = logging.getLogger(__name__)


@contextmanager
def _scheduler_lifespan(
    *,
    app: FastAPI,
    engine: Engine,
    queue_path: Path,
    intervention_window_us: int,
) -> Iterator[None]:
    """Open the queue and keep it available until the worker has stopped."""
    with closing(create_assessment_queue(path=queue_path)) as queue:
        scheduler = SchedulerState(queue=queue)
        worker = Thread(
            target=run_worker,
            kwargs={
                "scheduler": scheduler,
                "engine": engine,
                "now": app.state.clock,
                "intervention_window_us": intervention_window_us,
            },
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


def _log_started(*, engine: Engine, settings: Settings, log_path: Path) -> None:
    """Record the configuration that later decisions reference by model ID and version."""
    with read_session(engine=engine) as session:
        subject_speaker_id = get_subject_speaker_id(session=session)
        models = [
            {"model_id": model.model_id, "version": model.version, "type": model.type}
            for model in list_models(session=session)
        ]
    logger.info(
        "Application started",
        extra={
            "event": "app.started",
            "log_file": str(log_path),
            "schema_revision": get_schema_revision(engine=engine),
            "subject_speaker_id": subject_speaker_id,
            "intervention_window_us": settings.intervention_window_us,
            "models": models,
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
            initialize_experiment_config(
                engine=engine,
                subject_speaker_id=settings.subject_speaker_id,
                now=app.state.clock,
            )
            app.state.engine = engine
            stage = "queue"
            with _scheduler_lifespan(
                app=app,
                engine=engine,
                queue_path=settings.assessment_queue_path,
                intervention_window_us=settings.intervention_window_us,
            ):
                _log_started(engine=engine, settings=settings, log_path=log_path)
                stage = "running"
                yield
        finally:
            app.state.engine = None
            app.state.assessment_queue = None
            app.state.scheduler = None
            app.state.assessment_worker = None
            engine.dispose()
    except Exception:
        if stage != "running":
            logger.exception(
                "Application startup failed", extra={"event": "app.start_failed", "stage": stage}
            )
        raise
    finally:
        if stage == "running":
            logger.info("Application stopped", extra={"event": "app.stopped"})
        stop_logging()
