import asyncio
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi import Request
from fastapi import Response

from normative_conformance.config import Settings
from normative_conformance.config import get_settings

# Importing main builds the default ASGI object. Disable dotenv reads during that
# import; no application lifespan or HTTP client is started by these tests.
with patch.dict(Settings.model_config, {"env_file": None}):
    from normative_conformance import main
get_settings.cache_clear()


@pytest.mark.parametrize("failure", [False, True])
def test_metadata_assigns_server_identity_and_preserves_response_or_failure(*, failure):
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/example",
            "headers": [(b"x-request-id", b"client-supplied")],
        }
    )
    response = Response(status_code=202)
    error = RuntimeError("Handler failed")
    call_next = AsyncMock(return_value=response, side_effect=error if failure else None)
    if failure:
        with pytest.raises(RuntimeError) as caught:
            asyncio.run(main.response_metadata(request, call_next))
        assert caught.value is error
    else:
        assert asyncio.run(main.response_metadata(request, call_next)) is response
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["X-Request-ID"] == str(request.state.request_id)
        assert response.status_code == 202
    assert isinstance(request.state.request_id, UUID)
    assert request.state.request_id.version == 4
    call_next.assert_awaited_once_with(request)


@pytest.mark.parametrize("use_default", [False, True])
def test_application_wires_supplied_settings_clock_routes_and_handlers(*, monkeypatch, use_default):
    settings = Settings(_env_file=None, app_name="Unit application", debug=True)
    settings_loader = Mock(return_value=settings)
    monkeypatch.setattr(main, "get_settings", settings_loader)
    clock = Mock()
    application = Mock()
    factory = Mock(return_value=application)
    register = Mock()
    monkeypatch.setattr(main, "FastAPI", factory)
    monkeypatch.setattr(main, "register_error_handlers", register)
    assert main.create_app(settings=None if use_default else settings, now=clock) is application
    factory.assert_called_once_with(title="Unit application", debug=True, lifespan=main.lifespan)
    assert application.state.settings is settings
    assert application.state.clock is clock
    application.middleware.assert_called_once_with("http")
    application.middleware.return_value.assert_called_once_with(main.response_metadata)
    application.include_router.assert_called_once_with(main.router)
    register.assert_called_once_with(application=application)
    if use_default:
        settings_loader.assert_called_once_with()
    else:
        settings_loader.assert_not_called()
    clock.assert_not_called()
