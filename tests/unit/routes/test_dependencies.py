from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import Request
from fastapi import WebSocketException
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import HTTPConnection

from conversation_monitor.errors import ForeignRequest
from conversation_monitor.errors import NotReady
from conversation_monitor.errors import StorageUnavailable
from conversation_monitor.routes import dependencies


@pytest.mark.parametrize(
    "name,operation,message",
    [
        ("engine", dependencies.get_engine, "The application database is not initialized"),
        (
            "worker_stopped",
            dependencies.get_worker_stopped,
            "The assessment worker is not initialized",
        ),
        (
            "assessment_worker",
            dependencies.get_assessment_worker,
            "The assessment worker is not initialized",
        ),
    ],
)
def test_dependency_returns_an_initialized_resource_or_reports_it_missing(
    *, name, operation, message
):
    value = object()
    available = Request(
        {"type": "http", "app": SimpleNamespace(state=SimpleNamespace(**{name: value}))}
    )
    missing = Request({"type": "http", "app": SimpleNamespace(state=SimpleNamespace())})
    assert operation(request=available) is value
    with pytest.raises(NotReady) as caught:
        operation(request=missing)
    assert str(caught.value) == message


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


def connection(*, scope_type, headers):
    return HTTPConnection(
        {
            "type": scope_type,
            "headers": [(name.encode(), value.encode()) for name, value in headers.items()],
            "app": SimpleNamespace(
                state=SimpleNamespace(
                    settings=SimpleNamespace(allowed_hosts=["localhost", "127.0.0.1", "::1"])
                )
            ),
        }
    )


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({"host": "localhost:8000"}, id="script-on-this-machine"),
        pytest.param({"host": "127.0.0.1:8000"}, id="loopback-address"),
        pytest.param({"host": "[::1]:8000"}, id="ipv6-loopback"),
        pytest.param(
            {"host": "localhost:8000", "origin": "http://localhost:8000"}, id="capture-page"
        ),
    ],
)
@pytest.mark.parametrize("scope_type", ["http", "websocket"])
def test_local_clients_and_the_capture_page_are_allowed(*, scope_type, headers):
    assert (
        dependencies.reject_foreign_request(connection(scope_type=scope_type, headers=headers))
        is None
    )


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({}, id="no-host"),
        pytest.param({"host": "attacker.example"}, id="rebound-domain"),
        pytest.param({"host": "attacker.example:8000"}, id="rebound-domain-with-port"),
        pytest.param({"host": "localhost.attacker.example"}, id="allowed-name-as-prefix"),
        pytest.param({"host": "[malformed"}, id="malformed-host"),
        pytest.param(
            {"host": "localhost:8000", "origin": "https://attacker.example"}, id="other-site"
        ),
        pytest.param(
            {"host": "localhost:8000", "origin": "http://localhost:9000"}, id="other-port"
        ),
        pytest.param({"host": "localhost:8000", "origin": "null"}, id="sandboxed-page"),
        pytest.param({"host": "localhost:8000", "origin": "http://[malformed"}, id="bad-origin"),
    ],
)
def test_requests_from_other_sites_are_refused(*, headers):
    with pytest.raises(ForeignRequest):
        dependencies.reject_foreign_request(connection(scope_type="http", headers=headers))


def test_websockets_from_other_sites_close_before_they_are_accepted():
    with pytest.raises(WebSocketException) as caught:
        dependencies.reject_foreign_request(
            connection(
                scope_type="websocket",
                headers={"host": "localhost:8000", "origin": "https://attacker.example"},
            )
        )
    assert caught.value.code == 1008
