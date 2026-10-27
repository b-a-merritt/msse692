import logging
from threading import Event

from sqlalchemy import Engine
from typesafe_sdk import TypeSafeClient

from normative_conformance.schemas.internal import Clock
from normative_conformance.services.scheduler.run_worker.pending_cases import pending_cases
from normative_conformance.services.scheduler.run_worker.process_case import process_case

logger = logging.getLogger(__name__)


def run_worker(
    *,
    stopped: Event,
    engine: Engine,
    now: Clock,
    client: TypeSafeClient,
    batch_size: int,
    context_seconds: int,
) -> None:
    """Poll durable case progress with a 0.1-second idle wait."""
    try:
        while not stopped.is_set():
            try:
                # Each ready case gets one turn before any case is visited again.
                for case_id in pending_cases(engine=engine):
                    if stopped.is_set():
                        break
                    try:
                        process_case(
                            case_id=case_id,
                            batch_size=batch_size,
                            context_seconds=context_seconds,
                            engine=engine,
                            now=now,
                            client=client,
                        )
                    except Exception:
                        logger.exception(
                            "Case processing failed",
                            extra={
                                "event": "case.processing_failed",
                                "case_id": case_id,
                            },
                        )
            except Exception:
                logger.exception("Database polling failed", extra={"event": "worker.poll_failed"})
            stopped.wait(0.1)
    finally:
        stopped.set()
