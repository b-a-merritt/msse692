"""Intervention persistence, eligible sources, and delivery timestamps."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from normative_conformance import models


def _add_assessment(*, session, records, **changes):
    values = records["assessment"].model_dump()
    values.update(assessment_id=None, evaluation_id="evaluation-2")
    values.update(changes)
    assessment = models.Assessment(**values)
    session.add(assessment)
    session.flush()
    return assessment


def _add_source(*, session, records, assessment_id):
    session.add(
        models.InterventionSource(
            intervention_id=records["intervention"].intervention_id,
            assessment_id=assessment_id,
        )
    )
    session.commit()


def test_intervention_round_trip_with_defaults_and_generated_id(*, session, records):
    original = records["intervention"]
    assert original.intervention_id > 0
    assert original.sent_at_us is None
    stored = session.get(models.Intervention, original.intervention_id)
    assert stored is not None
    assert stored.model_dump() == original.model_dump()


def test_intervention_source_round_trip(*, session, records):
    original = records["intervention_source"]
    stored = session.get(
        models.InterventionSource, (original.intervention_id, original.assessment_id)
    )
    assert stored is not None
    assert stored.model_dump() == original.model_dump()


@pytest.mark.parametrize(
    ("changes", "constraint"),
    [
        pytest.param({"case_id": "missing"}, "FOREIGN KEY", id="missing-case"),
        pytest.param({"intervention_id": 0}, "CHECK", id="nonpositive-id"),
    ],
)
def test_invalid_interventions_are_rejected(*, session, records, changes, constraint):
    values = records["intervention"].model_dump() | {"intervention_id": None} | changes
    session.add(models.Intervention(**values))
    with pytest.raises(IntegrityError, match=constraint):
        session.commit()


def test_intervention_can_have_several_sources(*, session, records):
    assessment = _add_assessment(session=session, records=records)
    _add_source(session=session, records=records, assessment_id=assessment.assessment_id)
    sources = session.exec(
        select(models.InterventionSource.assessment_id).where(
            models.InterventionSource.intervention_id == records["intervention"].intervention_id
        )
    ).all()
    assert set(sources) == {records["assessment"].assessment_id, assessment.assessment_id}


def test_assessment_cannot_source_two_interventions(*, session, records):
    other = models.Intervention(case_id="case", message="Other", created_at_us=12)
    session.add(other)
    session.flush()
    session.add(
        models.InterventionSource(
            intervention_id=other.intervention_id,
            assessment_id=records["assessment"].assessment_id,
        )
    )
    with pytest.raises(IntegrityError, match="UNIQUE"):
        session.commit()


@pytest.mark.parametrize("status", ["non-conformant", "pending", "conflicted"])
def test_unconfirmed_assessments_cannot_be_sources(*, session, records, status):
    assessment = _add_assessment(session=session, records=records, status=status)
    with pytest.raises(IntegrityError, match="eligible assessment"):
        _add_source(session=session, records=records, assessment_id=assessment.assessment_id)


def test_repair_matches_cannot_be_sources(*, session, records):
    # The seeded apology model has the repairs type.
    assessment = _add_assessment(session=session, records=records, model_id="apology")
    with pytest.raises(IntegrityError, match="eligible assessment"):
        _add_source(session=session, records=records, assessment_id=assessment.assessment_id)


def test_sources_must_share_the_intervention_case(*, session, records):
    session.add(models.CaseLog(case_id="other", created_at_us=1))
    session.flush()
    session.add(models.Observation(**(records["observation"].model_dump() | {"case_id": "other"})))
    session.flush()
    assessment = _add_assessment(session=session, records=records, case_id="other")
    with pytest.raises(IntegrityError, match="eligible assessment"):
        _add_source(session=session, records=records, assessment_id=assessment.assessment_id)


def test_missing_assessments_cannot_be_sources(*, session, records):
    with pytest.raises(IntegrityError, match="eligible assessment"):
        _add_source(session=session, records=records, assessment_id=999)


def test_intervention_sources_are_immutable(*, session, records):
    original = records["intervention_source"]
    source = session.get(
        models.InterventionSource, (original.intervention_id, original.assessment_id)
    )
    session.delete(source)
    with pytest.raises(IntegrityError, match="intervention source is immutable"):
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


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"sent_at_us": 14}, id="resent"),
        pytest.param({"sent_at_us": None}, id="unsent"),
    ],
)
def test_intervention_is_marked_sent_only_once(*, session, records, changes):
    intervention = session.get(models.Intervention, records["intervention"].intervention_id)
    intervention.sent_at_us = 13
    session.commit()
    for name, value in changes.items():
        setattr(intervention, name, value)
    with pytest.raises(IntegrityError, match="marked sent once"):
        session.commit()


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"message": "Changed"}, id="message"),
        pytest.param({"created_at_us": 1}, id="created-at"),
    ],
)
def test_intervention_decision_is_immutable(*, session, records, changes):
    intervention = session.get(models.Intervention, records["intervention"].intervention_id)
    for name, value in changes.items():
        setattr(intervention, name, value)
    intervention.sent_at_us = 13
    with pytest.raises(IntegrityError, match="marked sent once"):
        session.commit()


def test_intervention_is_retained(*, session, records):
    intervention = session.get(models.Intervention, records["intervention"].intervention_id)
    session.delete(intervention)
    with pytest.raises(IntegrityError, match="intervention is retained"):
        session.commit()
