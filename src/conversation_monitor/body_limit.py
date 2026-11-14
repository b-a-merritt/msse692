from fastapi import Request
from starlette.types import ASGIApp
from starlette.types import Message
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send

from conversation_monitor.routes.errors import error_response

# Holds a maximum transcript in JSON with every character escaped, plus the other fields.
MAX_BODY_BYTES = 128 * 1024


def body_limit(app: ASGIApp) -> ASGIApp:
    """Read each request body up to a limit before anything parses or stores it."""

    async def limited(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await app(scope, receive, send)
            return

        messages: list[Message] = []
        size = 0
        while True:
            message = await receive()
            messages.append(message)
            size += len(message.get("body", b""))
            if size > MAX_BODY_BYTES:
                response = error_response(
                    request=Request(scope),
                    status=413,
                    code="BODY_TOO_LARGE",
                    message="The request body is too large",
                )
                await response(scope, receive, send)
                return
            if not message.get("more_body", False):
                break

        pending = iter(messages)

        async def replay() -> Message:
            return next(pending, None) or await receive()

        await app(scope, replay, send)

    return limited
