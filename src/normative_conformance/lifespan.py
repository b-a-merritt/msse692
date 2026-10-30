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
from typesafe_sdk import RetryPolicy
from typesafe_sdk import TypeSafeClient

from normative_conformance.config import Settings
from normative_conformance.database import create_database_engine
from normative_conformance.database import get_schema_revision
from normative_conformance.database import initialize_database
from normative_conformance.logging import start_logging
from normative_conformance.logging import stop_logging
from normative_conformance.services.scheduler.run_worker.run_worker import run_worker

logger = logging.getLogger(__name__)


@contextmanager
def _worker_lifespan(
    *,
    app: FastAPI,
    engine: Engine,
    client: TypeSafeClient,
    max_batch_seconds: int,
    max_batch_turns: int,
    idle_seconds: int,
    context_seconds: int,
) -> Iterator[None]:
    """Keep the database available until the worker has stopped."""
    stopped = Event()
    worker = Thread(
        target=run_worker,
        kwargs={
            "stopped": stopped,
            "engine": engine,
            "now": app.state.clock,
            "client": client,
            "max_batch_seconds": max_batch_seconds,
            "max_batch_turns": max_batch_turns,
            "idle_seconds": idle_seconds,
            "context_seconds": context_seconds,
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
) -> None:
    """Record the configuration used for live assessments."""
    logger.info(
        "Application started",
        extra={
            "event": "app.started",
            "log_file": str(log_path),
            "schema_revision": get_schema_revision(engine=engine),
            "decision_max_batch_seconds": settings.decision_max_batch_seconds,
            "decision_max_batch_turns": settings.decision_max_batch_turns,
            "decision_idle_seconds": settings.decision_idle_seconds,
            "decision_context_seconds": settings.decision_context_seconds,
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

            app.state.engine = engine
            stage = "jev"
            with TypeSafeClient(
                api_key=settings.type_safe_api_key,
                timeout=30,
                retry=RetryPolicy(max_retries=0),
            ) as client:
                stage = "worker"
                with _worker_lifespan(
                    app=app,
                    engine=engine,
                    client=client,
                    max_batch_seconds=settings.decision_max_batch_seconds,
                    max_batch_turns=settings.decision_max_batch_turns,
                    idle_seconds=settings.decision_idle_seconds,
                    context_seconds=settings.decision_context_seconds,
                ):
                    _log_started(engine=engine, settings=settings, log_path=log_path)
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
