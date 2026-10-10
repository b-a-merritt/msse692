from datetime import timezone
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from normative_conformance import config


@pytest.mark.parametrize(
    "values",
    [
        {"subject_speaker_id": ""},
        {"subject_speaker_id": "path/segment"},
        {"intervention_window_us": 0},
    ],
)
def test_invalid_runtime_settings_are_rejected_without_loading_env_files(*, values):
    with pytest.raises(ValidationError):
        config.Settings(_env_file=None, **values)


def test_settings_are_cached_until_cleared(*, monkeypatch):
    config.get_settings.cache_clear()
    constructor = Mock()
    monkeypatch.setattr(config, "Settings", constructor)
    try:
        assert config.get_settings() is constructor.return_value
        assert config.get_settings() is constructor.return_value
        constructor.assert_called_once_with()
        assert config.get_settings.cache_info().hits == 1
    finally:
        config.get_settings.cache_clear()


def test_runtime_clock_is_timezone_aware_utc():
    assert config.utc_now().tzinfo is timezone.utc
