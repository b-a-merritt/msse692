"""Intervention persistence, eligible sources, and delivery timestamps."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from normative_conformance import models


def test_intervention_round_trip_with_defaults_and_generated_id(*, session):
    case = models.CaseLog(case_id="case", created_at_us=1)
    session.add(case)
    session.flush()
    intervention = models.Intervention(case_id="case", message="Feedback", created_at_us=12)
    session.add(intervention)
    session.flush()
    session.commit()
    session.expunge_all()
    records = {"case": case, "intervention": intervention}

    original = records["intervention"]
    assert original.intervention_id > 0
    assert original.sent_at_us is None
    stored = session.get(models.Intervention, original.intervention_id)
    assert stored is not None
    assert stored.model_dump() == original.model_dump()


def test_intervention_source_round_trip(*, session):
    case = models.CaseLog(case_id="case", created_at_us=1)
    session.add(case)
    session.flush()
    observation = models.Observation(
        case_id="case",
        observation_id="chunk",
        sequence=1,
        received_at_us=10,
        speaker_id="subject",
        start_at_us=1,
        end_at_us=9,
        transcript="Hello",
        signal_level_min=-30.0,
        signal_level_avg=-20.0,
        signal_level_max=-10.0,
    )
    session.add(observation)
    session.flush()
    model = models.NormativeModelVersion(
        model_id="anger",
        name="Anger",
        version="1",
        rules_json='[{"rule_id":"test"}]',
        parameters_json="{}",
    )
    session.add(model)
    session.flush()
    assessment = models.Assessment(
        evaluation_id="evaluation-1",
        case_id="case",
        model_id="anger",
        model_version="1",
        evaluated_at_us=11,
        through_sequence=1,
        status="conformant",
        explanation_json='{"reason_code":"satisfied"}',
    )
    session.add(assessment)
    session.flush()
    intervention = models.Intervention(case_id="case", message="Feedback", created_at_us=12)
    session.add(intervention)
    session.flush()
    intervention_source = models.InterventionSource(
        intervention_id=intervention.intervention_id, assessment_id=assessment.assessment_id
    )
    session.add(intervention_source)
    session.flush()
    session.commit()
    session.expunge_all()
    records = {
        "assessment": assessment,
        "case": case,
        "intervention": intervention,
        "intervention_source": intervention_source,
        "model": model,
        "observation": observation,
    }

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
def test_invalid_interventions_are_rejected(*, session, changes, constraint):
    case = models.CaseLog(case_id="case", created_at_us=1)
    session.add(case)
    session.flush()
    intervention = models.Intervention(case_id="case", message="Feedback", created_at_us=12)
    session.add(intervention)
    session.flush()
    session.commit()
    session.expunge_all()
    records = {"case": case, "intervention": intervention}

    values = records["intervention"].model_dump() | {"intervention_id": None} | changes
    session.add(models.Intervention(**values))
    with pytest.raises(IntegrityError, match=constraint):
        session.commit()


def test_intervention_can_have_several_sources(*, session):
    case = models.CaseLog(case_id="case", created_at_us=1)
    session.add(case)
    session.flush()
    observation = models.Observation(
        case_id="case",
        observation_id="chunk",
        sequence=1,
        received_at_us=10,
        speaker_id="subject",
        start_at_us=1,
        end_at_us=9,
        transcript="Hello",
        signal_level_min=-30.0,
        signal_level_avg=-20.0,
        signal_level_max=-10.0,
    )
    session.add(observation)
    session.flush()
    model = models.NormativeModelVersion(
        model_id="anger",
        name="Anger",
        version="1",
        rules_json='[{"rule_id":"test"}]',
        parameters_json="{}",
    )
    session.add(model)
    session.flush()
    assessment = models.Assessment(
        evaluation_id="evaluation-1",
        case_id="case",
        model_id="anger",
        model_version="1",
        evaluated_at_us=11,
        through_sequence=1,
        status="conformant",
        explanation_json='{"reason_code":"satisfied"}',
    )
    session.add(assessment)
    session.flush()
    intervention = models.Intervention(case_id="case", message="Feedback", created_at_us=12)
    session.add(intervention)
    session.flush()
    intervention_source = models.InterventionSource(
        intervention_id=intervention.intervention_id, assessment_id=assessment.assessment_id
    )
    session.add(intervention_source)
    session.flush()
    session.commit()
    session.expunge_all()
    records = {
        "assessment": assessment,
        "case": case,
        "intervention": intervention,
        "intervention_source": intervention_source,
        "model": model,
        "observation": observation,
    }

    assessment = models.Assessment(
        **(
            records["assessment"].model_dump()
            | {"assessment_id": None, "evaluation_id": "evaluation-2"}
        )
    )
    session.add(assessment)
    session.flush()
    session.add(
        models.InterventionSource(
            intervention_id=records["intervention"].intervention_id,
            assessment_id=assessment.assessment_id,
        )
    )
    session.commit()
    sources = session.exec(
        select(models.InterventionSource.assessment_id).where(
            models.InterventionSource.intervention_id == records["intervention"].intervention_id
        )
    ).all()
    assert set(sources) == {records["assessment"].assessment_id, assessment.assessment_id}


def test_assessment_cannot_source_two_interventions(*, session):
    case = models.CaseLog(case_id="case", created_at_us=1)
    session.add(case)
    session.flush()
    observation = models.Observation(
        case_id="case",
        observation_id="chunk",
        sequence=1,
        received_at_us=10,
        speaker_id="subject",
        start_at_us=1,
        end_at_us=9,
        transcript="Hello",
        signal_level_min=-30.0,
        signal_level_avg=-20.0,
        signal_level_max=-10.0,
    )
    session.add(observation)
    session.flush()
    model = models.NormativeModelVersion(
        model_id="anger",
        name="Anger",
        version="1",
        rules_json='[{"rule_id":"test"}]',
        parameters_json="{}",
    )
    session.add(model)
    session.flush()
    assessment = models.Assessment(
        evaluation_id="evaluation-1",
        case_id="case",
        model_id="anger",
        model_version="1",
        evaluated_at_us=11,
        through_sequence=1,
        status="conformant",
        explanation_json='{"reason_code":"satisfied"}',
    )
    session.add(assessment)
    session.flush()
    session.commit()
    session.expunge_all()
    records = {"assessment": assessment, "case": case, "model": model, "observation": observation}

    first = models.Intervention(case_id="case", message="First", created_at_us=12)
    session.add(first)
    session.flush()
    session.add(
        models.InterventionSource(
            intervention_id=first.intervention_id,
            assessment_id=assessment.assessment_id,
        )
    )
    session.commit()

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
def test_unconfirmed_assessments_cannot_be_sources(*, session, status):
    case = models.CaseLog(case_id="case", created_at_us=1)
    session.add(case)
    session.flush()
    observation = models.Observation(
        case_id="case",
        observation_id="chunk",
        sequence=1,
        received_at_us=10,
        speaker_id="subject",
        start_at_us=1,
        end_at_us=9,
        transcript="Hello",
        signal_level_min=-30.0,
        signal_level_avg=-20.0,
        signal_level_max=-10.0,
    )
    session.add(observation)
    session.flush()
    model = models.NormativeModelVersion(
        model_id="anger",
        name="Anger",
        version="1",
        rules_json='[{"rule_id":"test"}]',
        parameters_json="{}",
    )
    session.add(model)
    session.flush()
    assessment = models.Assessment(
        evaluation_id="evaluation-1",
        case_id="case",
        model_id="anger",
        model_version="1",
        evaluated_at_us=11,
        through_sequence=1,
        status="conformant",
        explanation_json='{"reason_code":"satisfied"}',
    )
    session.add(assessment)
    session.flush()
    intervention = models.Intervention(case_id="case", message="Feedback", created_at_us=12)
    session.add(intervention)
    session.flush()
    intervention_source = models.InterventionSource(
        intervention_id=intervention.intervention_id, assessment_id=assessment.assessment_id
    )
    session.add(intervention_source)
    session.flush()
    session.commit()
    session.expunge_all()
    records = {
        "assessment": assessment,
        "case": case,
        "intervention": intervention,
        "intervention_source": intervention_source,
        "model": model,
        "observation": observation,
    }

    assessment = models.Assessment(
        **(
            records["assessment"].model_dump()
            | {"assessment_id": None, "evaluation_id": "evaluation-2", "status": status}
        )
    )
    session.add(assessment)
    session.flush()
    with pytest.raises(IntegrityError, match="eligible assessment"):
        session.add(
            models.InterventionSource(
                intervention_id=records["intervention"].intervention_id,
                assessment_id=assessment.assessment_id,
            )
        )
        session.commit()


def test_repair_matches_cannot_be_sources(*, session):
    # The seeded apology model has the repairs type.
    case = models.CaseLog(case_id="case", created_at_us=1)
    session.add(case)
    session.flush()
    observation = models.Observation(
        case_id="case",
        observation_id="chunk",
        sequence=1,
        received_at_us=10,
        speaker_id="subject",
        start_at_us=1,
        end_at_us=9,
        transcript="Hello",
        signal_level_min=-30.0,
        signal_level_avg=-20.0,
        signal_level_max=-10.0,
    )
    session.add(observation)
    session.flush()
    model = models.NormativeModelVersion(
        model_id="anger",
        name="Anger",
        version="1",
        rules_json='[{"rule_id":"test"}]',
        parameters_json="{}",
    )
    session.add(model)
    session.flush()
    assessment = models.Assessment(
        evaluation_id="evaluation-1",
        case_id="case",
        model_id="anger",
        model_version="1",
        evaluated_at_us=11,
        through_sequence=1,
        status="conformant",
        explanation_json='{"reason_code":"satisfied"}',
    )
    session.add(assessment)
    session.flush()
    intervention = models.Intervention(case_id="case", message="Feedback", created_at_us=12)
    session.add(intervention)
    session.flush()
    intervention_source = models.InterventionSource(
        intervention_id=intervention.intervention_id, assessment_id=assessment.assessment_id
    )
    session.add(intervention_source)
    session.flush()
    session.commit()
    session.expunge_all()
    records = {
        "assessment": assessment,
        "case": case,
        "intervention": intervention,
        "intervention_source": intervention_source,
        "model": model,
        "observation": observation,
    }

    assessment = models.Assessment(
        **(
            records["assessment"].model_dump()
            | {"assessment_id": None, "evaluation_id": "evaluation-2", "model_id": "apology"}
        )
    )
    session.add(assessment)
    session.flush()
    with pytest.raises(IntegrityError, match="eligible assessment"):
        session.add(
            models.InterventionSource(
                intervention_id=records["intervention"].intervention_id,
                assessment_id=assessment.assessment_id,
            )
        )
        session.commit()


def test_sources_must_share_the_intervention_case(*, session):
    case = models.CaseLog(case_id="case", created_at_us=1)
    session.add(case)
    session.flush()
    observation = models.Observation(
        case_id="case",
        observation_id="chunk",
        sequence=1,
        received_at_us=10,
        speaker_id="subject",
        start_at_us=1,
        end_at_us=9,
        transcript="Hello",
        signal_level_min=-30.0,
        signal_level_avg=-20.0,
        signal_level_max=-10.0,
    )
    session.add(observation)
    session.flush()
    model = models.NormativeModelVersion(
        model_id="anger",
        name="Anger",
        version="1",
        rules_json='[{"rule_id":"test"}]',
        parameters_json="{}",
    )
    session.add(model)
    session.flush()
    assessment = models.Assessment(
        evaluation_id="evaluation-1",
        case_id="case",
        model_id="anger",
        model_version="1",
        evaluated_at_us=11,
        through_sequence=1,
        status="conformant",
        explanation_json='{"reason_code":"satisfied"}',
    )
    session.add(assessment)
    session.flush()
    intervention = models.Intervention(case_id="case", message="Feedback", created_at_us=12)
    session.add(intervention)
    session.flush()
    intervention_source = models.InterventionSource(
        intervention_id=intervention.intervention_id, assessment_id=assessment.assessment_id
    )
    session.add(intervention_source)
    session.flush()
    session.commit()
    session.expunge_all()
    records = {
        "assessment": assessment,
        "case": case,
        "intervention": intervention,
        "intervention_source": intervention_source,
        "model": model,
        "observation": observation,
    }

    session.add(models.CaseLog(case_id="other", created_at_us=1))
    session.flush()
    session.add(models.Observation(**(records["observation"].model_dump() | {"case_id": "other"})))
    session.flush()
    assessment = models.Assessment(
        **(
            records["assessment"].model_dump()
            | {"assessment_id": None, "evaluation_id": "evaluation-2", "case_id": "other"}
        )
    )
    session.add(assessment)
    session.flush()
    with pytest.raises(IntegrityError, match="eligible assessment"):
        session.add(
            models.InterventionSource(
                intervention_id=records["intervention"].intervention_id,
                assessment_id=assessment.assessment_id,
            )
        )
        session.commit()


def test_missing_assessments_cannot_be_sources(*, session):
    case = models.CaseLog(case_id="case", created_at_us=1)
    session.add(case)
    session.flush()
    observation = models.Observation(
        case_id="case",
        observation_id="chunk",
        sequence=1,
        received_at_us=10,
        speaker_id="subject",
        start_at_us=1,
        end_at_us=9,
        transcript="Hello",
        signal_level_min=-30.0,
        signal_level_avg=-20.0,
        signal_level_max=-10.0,
    )
    session.add(observation)
    session.flush()
    model = models.NormativeModelVersion(
        model_id="anger",
        name="Anger",
        version="1",
        rules_json='[{"rule_id":"test"}]',
        parameters_json="{}",
    )
    session.add(model)
    session.flush()
    assessment = models.Assessment(
        evaluation_id="evaluation-1",
        case_id="case",
        model_id="anger",
        model_version="1",
        evaluated_at_us=11,
        through_sequence=1,
        status="conformant",
        explanation_json='{"reason_code":"satisfied"}',
    )
    session.add(assessment)
    session.flush()
    intervention = models.Intervention(case_id="case", message="Feedback", created_at_us=12)
    session.add(intervention)
    session.flush()
    intervention_source = models.InterventionSource(
        intervention_id=intervention.intervention_id, assessment_id=assessment.assessment_id
    )
    session.add(intervention_source)
    session.flush()
    session.commit()
    session.expunge_all()
    records = {
        "assessment": assessment,
        "case": case,
        "intervention": intervention,
        "intervention_source": intervention_source,
        "model": model,
        "observation": observation,
    }

    with pytest.raises(IntegrityError, match="eligible assessment"):
        session.add(
            models.InterventionSource(
                intervention_id=records["intervention"].intervention_id, assessment_id=999
            )
        )
        session.commit()


def test_intervention_sources_are_immutable(*, session):
    case = models.CaseLog(case_id="case", created_at_us=1)
    session.add(case)
    session.flush()
    observation = models.Observation(
        case_id="case",
        observation_id="chunk",
        sequence=1,
        received_at_us=10,
        speaker_id="subject",
        start_at_us=1,
        end_at_us=9,
        transcript="Hello",
        signal_level_min=-30.0,
        signal_level_avg=-20.0,
        signal_level_max=-10.0,
    )
    session.add(observation)
    session.flush()
    model = models.NormativeModelVersion(
        model_id="anger",
        name="Anger",
        version="1",
        rules_json='[{"rule_id":"test"}]',
        parameters_json="{}",
    )
    session.add(model)
    session.flush()
    assessment = models.Assessment(
        evaluation_id="evaluation-1",
        case_id="case",
        model_id="anger",
        model_version="1",
        evaluated_at_us=11,
        through_sequence=1,
        status="conformant",
        explanation_json='{"reason_code":"satisfied"}',
    )
    session.add(assessment)
    session.flush()
    intervention = models.Intervention(case_id="case", message="Feedback", created_at_us=12)
    session.add(intervention)
    session.flush()
    intervention_source = models.InterventionSource(
        intervention_id=intervention.intervention_id, assessment_id=assessment.assessment_id
    )
    session.add(intervention_source)
    session.flush()
    session.commit()
    session.expunge_all()
    records = {
        "assessment": assessment,
        "case": case,
        "intervention": intervention,
        "intervention_source": intervention_source,
        "model": model,
        "observation": observation,
    }

    original = records["intervention_source"]
    source = session.get(
        models.InterventionSource, (original.intervention_id, original.assessment_id)
    )
    session.delete(source)
    with pytest.raises(IntegrityError, match="intervention source is immutable"):
        session.commit()


@pytest.mark.parametrize("sent_at_us", [12, 13])
def test_intervention_can_be_marked_sent(*, session, sent_at_us):
    case = models.CaseLog(case_id="case", created_at_us=1)
    session.add(case)
    session.flush()
    intervention = models.Intervention(case_id="case", message="Feedback", created_at_us=12)
    session.add(intervention)
    session.flush()
    session.commit()
    session.expunge_all()
    records = {"case": case, "intervention": intervention}

    intervention = session.get(models.Intervention, records["intervention"].intervention_id)
    intervention.sent_at_us = sent_at_us
    session.commit()
    session.refresh(intervention)
    assert intervention.sent_at_us == sent_at_us


def test_intervention_cannot_be_sent_before_creation(*, session):
    case = models.CaseLog(case_id="case", created_at_us=1)
    session.add(case)
    session.flush()
    intervention = models.Intervention(case_id="case", message="Feedback", created_at_us=12)
    session.add(intervention)
    session.flush()
    session.commit()
    session.expunge_all()
    records = {"case": case, "intervention": intervention}

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
def test_intervention_is_marked_sent_only_once(*, session, changes):
    case = models.CaseLog(case_id="case", created_at_us=1)
    session.add(case)
    session.flush()
    intervention = models.Intervention(case_id="case", message="Feedback", created_at_us=12)
    session.add(intervention)
    session.flush()
    session.commit()
    session.expunge_all()
    records = {"case": case, "intervention": intervention}

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
def test_intervention_decision_is_immutable(*, session, changes):
    case = models.CaseLog(case_id="case", created_at_us=1)
    session.add(case)
    session.flush()
    intervention = models.Intervention(case_id="case", message="Feedback", created_at_us=12)
    session.add(intervention)
    session.flush()
    session.commit()
    session.expunge_all()
    records = {"case": case, "intervention": intervention}

    intervention = session.get(models.Intervention, records["intervention"].intervention_id)
    for name, value in changes.items():
        setattr(intervention, name, value)
    intervention.sent_at_us = 13
    with pytest.raises(IntegrityError, match="marked sent once"):
        session.commit()


def test_intervention_is_retained(*, session):
    case = models.CaseLog(case_id="case", created_at_us=1)
    session.add(case)
    session.flush()
    intervention = models.Intervention(case_id="case", message="Feedback", created_at_us=12)
    session.add(intervention)
    session.flush()
    session.commit()
    session.expunge_all()
    records = {"case": case, "intervention": intervention}

    intervention = session.get(models.Intervention, records["intervention"].intervention_id)
    session.delete(intervention)
    with pytest.raises(IntegrityError, match="intervention is retained"):
        session.commit()
