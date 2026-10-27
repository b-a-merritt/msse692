import asyncio
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import Request
from fastapi import Response

from normative_conformance.middleware import response_metadata


def test_metadata_assigns_server_identity_and_headers():
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/example",
            "headers": [(b"x-request-id", b"client-supplied")],
        }
    )
    response = Response(status_code=202)
    call_next = AsyncMock(return_value=response)
    assert asyncio.run(response_metadata(request, call_next)) is response
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Request-ID"] == str(request.state.request_id)
    assert response.status_code == 202
    assert request.state.request_id.version == 4
    call_next.assert_awaited_once_with(request)


def test_metadata_assigns_server_identity_before_a_handler_failure():
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/example",
            "headers": [(b"x-request-id", b"client-supplied")],
        }
    )
    error = RuntimeError("Handler failed")
    call_next = AsyncMock(side_effect=error)
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(response_metadata(request, call_next))
    assert caught.value is error
    assert isinstance(request.state.request_id, UUID)
    assert request.state.request_id.version == 4
    call_next.assert_awaited_once_with(request)
