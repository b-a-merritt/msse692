from unittest.mock import Mock
from unittest.mock import patch

from normative_conformance.config import Settings
from normative_conformance.config import get_settings

# Importing main builds the default ASGI object. Disable dotenv reads during that
# import; no application lifespan or HTTP client is started by these tests.
with patch.dict(Settings.model_config, {"env_file": None}):
    from normative_conformance import main
get_settings.cache_clear()


def test_application_wires_supplied_settings_clock_routes_and_handlers(*, monkeypatch):
    settings = Settings(_env_file=None, app_name="Unit application", debug=True)
    settings_loader = Mock(return_value=settings)
    monkeypatch.setattr(main, "get_settings", settings_loader)
    clock = Mock()
    application = Mock()
    factory = Mock(return_value=application)
    register = Mock()
    monkeypatch.setattr(main, "FastAPI", factory)
    monkeypatch.setattr(main, "register_error_handlers", register)
    assert main.create_app(settings=settings, now=clock) is application
    factory.assert_called_once_with(title="Unit application", debug=True, lifespan=main.lifespan)
    assert application.state.settings is settings
    assert application.state.clock is clock
    application.middleware.assert_called_once_with("http")
    application.middleware.return_value.assert_called_once_with(main.response_metadata)
    application.include_router.assert_called_once_with(main.router)
    register.assert_called_once_with(application=application)
    settings_loader.assert_not_called()
    clock.assert_not_called()


def test_application_loads_default_settings_when_none_are_supplied(*, monkeypatch):
    settings = Settings(_env_file=None, app_name="Default application")
    settings_loader = Mock(return_value=settings)
    monkeypatch.setattr(main, "get_settings", settings_loader)
    monkeypatch.setattr(main, "FastAPI", Mock())
    monkeypatch.setattr(main, "register_error_handlers", Mock())
    application = main.create_app(settings=None, now=Mock())
    settings_loader.assert_called_once_with()
    assert application.state.settings is settings
