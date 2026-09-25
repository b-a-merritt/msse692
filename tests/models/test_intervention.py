"""Intervention persistence, assessment references, and delivery timestamps."""

import pytest
from sqlalchemy.exc import IntegrityError

from normative_conformance import models


def test_intervention_round_trip_with_defaults_and_generated_id(*, session, records):
    original = records["intervention"]
    assert original.intervention_id > 0
    assert original.sent_at_us is None
    stored = session.get(models.Intervention, original.intervention_id)
    assert stored is not None
    assert stored.model_dump() == original.model_dump()


@pytest.mark.parametrize(
    ("changes", "constraint"),
    [
        pytest.param({}, "UNIQUE", id="duplicate-assessment"),
        pytest.param({"assessment_id": 999}, "FOREIGN KEY", id="missing-assessment"),
        pytest.param({"intervention_id": 0}, "CHECK", id="nonpositive-id"),
    ],
)
def test_invalid_interventions_are_rejected(*, session, records, changes, constraint):
    values = records["intervention"].model_dump() | {"intervention_id": None} | changes
    session.add(models.Intervention(**values))
    with pytest.raises(IntegrityError, match=constraint):
        session.commit()


@pytest.mark.parametrize("sent_at_us", [12, 13])
def test_intervention_can_be_marked_sent(*, session, records, sent_at_us):
    intervention = session.get(models.Intervention, records["intervention"].intervention_id)
    intervention.sent_at_us = sent_at_us
    session.commit()
    session.refresh(intervention)
    assert intervention.sent_at_us == sent_at_us


def test_intervention_cannot_be_sent_before_creation(*, session, records):
    intervention = session.get(models.Intervention, records["intervention"].intervention_id)
    intervention.sent_at_us = 11
    with pytest.raises(IntegrityError, match="CHECK constraint failed"):
        session.commit()
    session.rollback()
    assert intervention.sent_at_us is None
