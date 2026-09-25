"""Persistence and singleton configuration for case models."""

import pytest
from sqlalchemy.exc import IntegrityError

from normative_conformance import models


def test_case_round_trip(*, session, records):
    original = records["case"]
    stored = session.get(models.CaseLog, original.case_id)
    assert stored is not None
    assert stored.model_dump() == original.model_dump()


def test_experiment_round_trip_with_default_id(*, session, records):
    original = records["experiment"]
    assert original.experiment_id == 1
    stored = session.get(models.ExperimentConfig, original.experiment_id)
    assert stored is not None
    assert stored.model_dump() == original.model_dump()


@pytest.mark.parametrize("experiment_id", [0, 2])
def test_experiment_is_a_singleton(*, session, experiment_id):
    session.add(
        models.ExperimentConfig(
            experiment_id=experiment_id, subject_speaker_id="subject", created_at_us=1
        )
    )
    with pytest.raises(IntegrityError, match="CHECK constraint failed"):
        session.commit()
