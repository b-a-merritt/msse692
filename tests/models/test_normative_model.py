"""Normative model version persistence and JSON constraints."""

import pytest
from sqlalchemy.exc import IntegrityError

from normative_conformance import models


def test_model_version_round_trip(*, session, records):
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
    ],
)
def test_invalid_model_versions_are_rejected(*, session, records, changes, constraint):
    values = records["model"].model_dump() | {"version": "2"} | changes
    session.add(models.NormativeModelVersion(**values))
    with pytest.raises(IntegrityError, match=constraint):
        session.commit()
