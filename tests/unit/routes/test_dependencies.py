from contextlib import nullcontext
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import Request
from sqlalchemy.exc import SQLAlchemyError

from normative_conformance.errors import NotReady
from normative_conformance.errors import StorageUnavailable
from normative_conformance.routes import dependencies


@pytest.mark.parametrize(
    "name,operation,message",
    [
        ("engine", dependencies.get_engine, "The application database is not initialized"),
        ("scheduler", dependencies.get_scheduler, "The assessment worker is not running"),
        (
            "assessment_worker",
            dependencies.get_assessment_worker,
            "The assessment worker is not initialized",
        ),
    ],
)
@pytest.mark.parametrize("available", [False, True])
def test_dependency_requires_an_initialized_resource(*, name, operation, message, available):
    value = SimpleNamespace(stopped=Event()) if name == "scheduler" else object()
    state = SimpleNamespace(**({name: value} if available else {}))
    request = Request({"type": "http", "app": SimpleNamespace(state=state)})
    if available:
        assert operation(request=request) is value
    else:
        with pytest.raises(NotReady) as caught:
            operation(request=request)
        assert str(caught.value) == message


def test_stopped_scheduler_is_not_available():
    stopped = Event()
    stopped.set()
    request = Request(
        {
            "type": "http",
            "app": SimpleNamespace(
                state=SimpleNamespace(scheduler=SimpleNamespace(stopped=stopped))
            ),
        }
    )
    with pytest.raises(NotReady, match=r"^The assessment worker is not running$"):
        dependencies.get_scheduler(request=request)


def test_clock_is_supplied_without_reading_it():
    clock = Mock()
    request = Request({"type": "http", "app": SimpleNamespace(state=SimpleNamespace(clock=clock))})
    assert dependencies.get_clock(request=request) is clock
    clock.assert_not_called()


@pytest.mark.parametrize("write", [False, True])
def test_session_provider_yields_the_configured_resource(*, monkeypatch, write):
    engine = object()
    session = object()
    request = Request(
        {"type": "http", "app": SimpleNamespace(state=SimpleNamespace(engine=engine))}
    )
    context = Mock(return_value=nullcontext(session))
    monkeypatch.setattr(dependencies, "write_session" if write else "read_session", context)
    generator = (dependencies.get_write_session if write else dependencies.get_read_session)(
        request=request
    )
    assert next(generator) is session
    with pytest.raises(StopIteration):
        next(generator)
    context.assert_called_once_with(engine=engine)


def test_write_provider_translates_failures_from_the_request_body(*, monkeypatch):
    request = Request(
        {"type": "http", "app": SimpleNamespace(state=SimpleNamespace(engine=object()))}
    )
    monkeypatch.setattr(dependencies, "write_session", Mock(return_value=nullcontext(object())))
    generator = dependencies.get_write_session(request=request)
    next(generator)
    failure = SQLAlchemyError("Driver details")
    with pytest.raises(
        StorageUnavailable, match=r"^The application database is unavailable$"
    ) as caught:
        generator.throw(failure)
    assert caught.value.__cause__ is failure
