import pytest
from pydantic import ValidationError

from normative_conformance import config


@pytest.mark.parametrize(
    "field,value,error_type",
    [
        pytest.param("decision_max_batch_seconds", 0, "greater_than", id="zero-batch-duration"),
        pytest.param("decision_idle_seconds", 0, "greater_than", id="zero-idle-duration"),
        pytest.param("capture_max_seconds", 0, "greater_than", id="zero-capture-duration"),
        pytest.param("capture_max_connections", 0, "greater_than", id="no-capture-connections"),
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
