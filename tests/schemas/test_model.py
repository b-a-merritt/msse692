import pytest
from pydantic import ValidationError

from normative_conformance.schemas.model import ModelVersion


@pytest.mark.parametrize("allowance", [None, 1, 5_000_000])
def test_repair_allowance_accepts_none_or_positive_integer_microseconds(*, allowance):
    model = ModelVersion(
        model_id="example",
        name="Example",
        version="1",
        type="undesired",
        repair_allowance_us=allowance,
        rules=[{"rule_id": "match", "description": "Matches", "sql": "SELECT 1"}],
        parameters={},
    )

    assert model.repair_allowance_us == allowance
    assert "repairable" not in model.model_dump()


@pytest.mark.parametrize("allowance", [0, -1, True, False, 1.5, "10000000"])
def test_repair_allowance_rejects_invalid_durations(*, allowance):
    with pytest.raises(ValidationError):
        ModelVersion(
            model_id="example",
            name="Example",
            version="1",
            type="undesired",
            repair_allowance_us=allowance,
            rules=[{"rule_id": "match", "description": "Matches", "sql": "SELECT 1"}],
            parameters={},
        )
