from threading import Event
from threading import Thread

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session
from sqlmodel import select

from normative_conformance.errors import NotReady
from normative_conformance.schemas.health import Readiness


def readiness(
    *,
    session: Session,
    stopped: Event,
    worker: Thread,
) -> Readiness:
    """Check the ingestion runtime without changing records."""
    if stopped.is_set() or not worker.is_alive():
        raise NotReady("The assessment worker is not running")

    try:
        session.exec(select(1)).one()
    except SQLAlchemyError as error:
        raise NotReady("The application database is unavailable") from error

    return Readiness(status="ready")
