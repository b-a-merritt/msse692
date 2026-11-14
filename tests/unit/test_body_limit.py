import asyncio
import json
from uuid import UUID

from conversation_monitor.body_limit import MAX_BODY_BYTES
from conversation_monitor.body_limit import body_limit


def http_scope():
    return {
        "type": "http",
        "method": "POST",
        "path": "/example",
        "headers": [],
        "state": {"request_id": UUID(int=1)},
    }


def server_messages(*messages):
    remaining = iter(messages)

    async def receive():
        return next(remaining)

    return receive


def run(*, scope, receive):
    """Return what the wrapped application read and what the client was sent."""
    read = []
    sent = []

    async def application(scope, app_receive, send):
        while True:
            message = await app_receive()
            read.append(message)
            if not message.get("more_body", False):
                return

    async def send(message):
        sent.append(message)

    asyncio.run(body_limit(application)(scope, receive, send))
    return read, sent


def test_body_at_the_limit_reaches_the_application_unchanged():
    body = b"x" * MAX_BODY_BYTES

    read, sent = run(
        scope=http_scope(),
        receive=server_messages({"type": "http.request", "body": body, "more_body": False}),
    )

    assert read == [{"type": "http.request", "body": body, "more_body": False}]
    assert sent == []


def test_chunks_are_replayed_in_order():
    first = {"type": "http.request", "body": b"first", "more_body": True}
    second = {"type": "http.request", "body": b"second", "more_body": False}

    read, sent = run(scope=http_scope(), receive=server_messages(first, second))

    assert read == [first, second]
    assert sent == []


def test_body_over_the_limit_is_refused_before_the_application_runs():
    read, sent = run(
        scope=http_scope(),
        receive=server_messages(
            {"type": "http.request", "body": b"x" * (MAX_BODY_BYTES + 1), "more_body": False}
        ),
    )

    assert read == []
    assert sent[0]["status"] == 413
    assert json.loads(sent[1]["body"]) == {
        "error": {
            "code": "BODY_TOO_LARGE",
            "message": "The request body is too large",
            "request_id": str(UUID(int=1)),
        }
    }


def test_small_chunks_that_add_up_over_the_limit_are_refused():
    chunk = b"x" * (MAX_BODY_BYTES // 2 + 1)

    read, sent = run(
        scope=http_scope(),
        receive=server_messages(
            {"type": "http.request", "body": chunk, "more_body": True},
            {"type": "http.request", "body": chunk, "more_body": True},
        ),
    )

    assert read == []
    assert sent[0]["status"] == 413


def test_client_disconnect_during_upload_reaches_the_application():
    partial = {"type": "http.request", "body": b"partial", "more_body": True}
    disconnect = {"type": "http.disconnect"}

    read, sent = run(scope=http_scope(), receive=server_messages(partial, disconnect))

    assert read == [partial, disconnect]
    assert sent == []


def test_application_reads_past_the_replayed_body_from_the_server():
    body = {"type": "http.request", "body": b"", "more_body": False}
    disconnect = {"type": "http.disconnect"}
    read = []

    async def application(scope, receive, send):
        read.extend([await receive(), await receive()])

    async def send(message):
        raise AssertionError("The application sends nothing")

    asyncio.run(body_limit(application)(http_scope(), server_messages(body, disconnect), send))

    assert read == [body, disconnect]


def test_websockets_pass_through_without_reading_messages():
    seen = []

    async def application(scope, receive, send):
        seen.append(scope["type"])

    async def receive():
        raise AssertionError("WebSocket messages belong to the route")

    async def send(message):
        raise AssertionError("The application sends nothing")

    asyncio.run(body_limit(application)({"type": "websocket"}, receive, send))

    assert seen == ["websocket"]
