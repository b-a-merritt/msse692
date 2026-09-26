from collections.abc import Iterator
from typing import Annotated
from typing import cast

from fastapi import Depends
from fastapi import Request
from persistqueue import SQLiteAckQueue
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


def get_assessment_queue(*, request: Request) -> SQLiteAckQueue:
    queue = cast(SQLiteAckQueue | None, getattr(request.app.state, "assessment_queue", None))
    if queue is None:
        raise NotReady("The assessment queue is not initialized")
    return queue


ReadSession = Annotated[Session, Depends(get_read_session)]
WriteSession = Annotated[Session, Depends(get_write_session)]
ServerClock = Annotated[Clock, Depends(get_clock)]
AssessmentQueue = Annotated[SQLiteAckQueue, Depends(get_assessment_queue)]
