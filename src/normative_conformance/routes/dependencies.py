from collections.abc import Iterator
from threading import Event
from threading import Thread
from typing import Annotated
from typing import cast

from fastapi import Depends
from fastapi import Path
from fastapi import Request
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from normative_conformance.database import read_session
from normative_conformance.database import write_session
from normative_conformance.errors import NotReady
from normative_conformance.errors import StorageUnavailable
from normative_conformance.schemas.internal import Clock


def get_engine(
    *,
    request: Request,
) -> Engine:
    engine = cast(Engine | None, getattr(request.app.state, "engine", None))
    if engine is None:
        raise NotReady("The application database is not initialized")
    return engine


def get_read_session(
    *,
    request: Request,
) -> Iterator[Session]:
    """Provide a database session for a lookup request."""
    with read_session(engine=get_engine(request=request)) as session:
        yield session


def get_write_session(
    *,
    request: Request,
) -> Iterator[Session]:
    """Mutating services commit their stages; unfinished transactions roll back."""
    try:
        with write_session(engine=get_engine(request=request)) as session:
            yield session
    except SQLAlchemyError as error:
        raise StorageUnavailable("The application database is unavailable") from error


def get_clock(
    *,
    request: Request,
) -> Clock:
    return cast(Clock, request.app.state.clock)


def get_worker_stopped(*, request: Request) -> Event:
    stopped = cast(Event | None, getattr(request.app.state, "worker_stopped", None))
    if stopped is None:
        raise NotReady("The assessment worker is not initialized")
    return stopped


def get_assessment_worker(*, request: Request) -> Thread:
    worker = cast(Thread | None, getattr(request.app.state, "assessment_worker", None))
    if worker is None:
        raise NotReady("The assessment worker is not initialized")
    return worker


# A nonempty identity path segment.
PathId = Annotated[str, Path(strict=True, min_length=1, pattern=r"^[^/]+$")]

ReadSession = Annotated[Session, Depends(get_read_session)]
WriteSession = Annotated[Session, Depends(get_write_session)]
ServerClock = Annotated[Clock, Depends(get_clock)]
WorkerStopped = Annotated[Event, Depends(get_worker_stopped)]
AssessmentWorker = Annotated[Thread, Depends(get_assessment_worker)]
