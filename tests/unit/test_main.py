from unittest.mock import Mock
from unittest.mock import patch

from conversation_monitor.config import Settings
from conversation_monitor.config import get_settings

# Importing main builds the default ASGI object. Disable dotenv reads during that
# import; no application lifespan or HTTP client is started by these tests.
with patch.dict(Settings.model_config, {"env_file": None}):
    from conversation_monitor import main
get_settings.cache_clear()


def test_application_loads_default_settings_when_none_are_supplied(*, monkeypatch):
    settings = Settings(_env_file=None, app_name="Default application")
    settings_loader = Mock(return_value=settings)
    monkeypatch.setattr(main, "get_settings", settings_loader)
    monkeypatch.setattr(main, "FastAPI", Mock())
    monkeypatch.setattr(main, "register_error_handlers", Mock())
    application = main.create_app(settings=None, now=Mock())
    settings_loader.assert_called_once_with()
    assert application.state.settings is settings
