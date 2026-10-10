"""Normative model version persistence and JSON constraints."""

import pytest
from sqlalchemy.exc import IntegrityError

from normative_conformance import models


def test_model_version_round_trip(*, session):
    model = models.NormativeModelVersion(
        model_id="anger",
        name="Anger",
        version="1",
        rules_json='[{"rule_id":"test"}]',
        parameters_json="{}",
    )
    session.add(model)
    session.flush()
    session.commit()
    session.expunge_all()
    records = {"model": model}

    original = records["model"]
    stored = session.get(models.NormativeModelVersion, (original.model_id, original.version))
    assert stored is not None
    assert stored.model_dump() == original.model_dump()


@pytest.mark.parametrize(
    ("changes", "constraint"),
    [
        pytest.param({"version": "1"}, "UNIQUE", id="duplicate-version"),
        pytest.param({"rules_json": "invalid"}, "CHECK", id="invalid-rules-json"),
        pytest.param({"parameters_json": "invalid"}, "CHECK", id="invalid-parameters-json"),
        pytest.param({"type": "unknown"}, "CHECK", id="unknown-type"),
        pytest.param({"repair_allowance_us": 0}, "CHECK", id="zero-repair-allowance"),
        pytest.param({"repair_allowance_us": -1}, "CHECK", id="negative-repair-allowance"),
        pytest.param(
            {"type": "repairs", "repair_allowance_us": 1}, "CHECK", id="repair-with-allowance"
        ),
    ],
)
def test_invalid_model_versions_are_rejected(*, session, changes, constraint):
    model = models.NormativeModelVersion(
        model_id="anger",
        name="Anger",
        version="1",
        rules_json='[{"rule_id":"test"}]',
        parameters_json="{}",
    )
    session.add(model)
    session.flush()
    session.commit()
    session.expunge_all()
    records = {"model": model}

    values = records["model"].model_dump() | {"version": "2"} | changes
    session.add(models.NormativeModelVersion(**values))
    with pytest.raises(IntegrityError, match=constraint):
        session.commit()
