from datetime import timezone
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from normative_conformance import config


@pytest.mark.parametrize(
    "field,value,error_type",
    [
        pytest.param("decision_batch_size", 0, "greater_than", id="zero-batch-size"),
        pytest.param(
            "decision_context_seconds", -1, "greater_than_equal", id="negative-context-duration"
        ),
    ],
)
def test_invalid_runtime_settings_are_rejected_without_loading_env_files(
    *, field, value, error_type
):
    with pytest.raises(ValidationError) as caught:
        config.Settings(_env_file=None, **{field: value})

    assert [(error["loc"], error["type"]) for error in caught.value.errors()] == [
        ((field,), error_type)
    ]


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
