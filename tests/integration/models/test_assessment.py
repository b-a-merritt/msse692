"""Assessment persistence, model references, and saved evidence extents."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from normative_conformance import models


def test_assessment_round_trip_with_defaults_and_generated_id(*, session):
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

    original = records["assessment"]
    assert original.assessment_id > 0
    assert original.next_due_at_us is None
    stored = session.get(models.Assessment, original.assessment_id)
    assert stored is not None
    assert stored.model_dump() == original.model_dump()


@pytest.mark.parametrize(
    ("changes", "constraint"),
    [
        pytest.param({"assessment_id": 0}, "CHECK", id="nonpositive-id"),
        pytest.param({"evaluation_id": "evaluation-1"}, "UNIQUE", id="duplicate-evaluation"),
        pytest.param({"model_id": "missing"}, "FOREIGN KEY", id="missing-model"),
        pytest.param({"model_version": "missing"}, "FOREIGN KEY", id="missing-model-version"),
        pytest.param({"case_id": "missing"}, "FOREIGN KEY", id="missing-case"),
        pytest.param({"through_sequence": 2}, "FOREIGN KEY", id="missing-prefix-end"),
        pytest.param({"through_sequence": 0}, "CHECK", id="nonpositive-prefix-end"),
        pytest.param({"status": "invalid"}, "CHECK", id="invalid-status"),
        pytest.param({"explanation_json": "invalid"}, "CHECK", id="invalid-explanation-json"),
    ],
)
def test_invalid_assessments_are_rejected(*, session, changes, constraint):
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

    values = records["assessment"].model_dump()
    values.update(assessment_id=None, evaluation_id="evaluation-2")
    values.update(changes)
    session.add(models.Assessment(**values))
    with pytest.raises(IntegrityError, match=constraint):
        session.commit()


@pytest.mark.parametrize("status", ["conformant", "non-conformant", "pending", "conflicted"])
def test_new_evaluations_accept_all_statuses(*, session, status):
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

    values = records["assessment"].model_dump()
    values.update(
        assessment_id=None, evaluation_id="evaluation-2", status=status, next_due_at_us=20
    )
    assessment = models.Assessment(**values)
    session.add(assessment)
    session.commit()
    session.refresh(assessment)
    assert assessment.assessment_id != records["assessment"].assessment_id
    assert assessment.status == status
    assert assessment.next_due_at_us == 20


def test_evaluation_can_include_multiple_model_versions(*, session):
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

    session.add(models.NormativeModelVersion(**(records["model"].model_dump() | {"version": "2"})))
    session.flush()
    values = records["assessment"].model_dump() | {"assessment_id": None, "model_version": "2"}
    session.add(models.Assessment(**values))
    session.commit()
    assessments = session.exec(select(models.Assessment)).all()
    assert {(row.evaluation_id, row.model_version) for row in assessments} == {
        ("evaluation-1", "1"),
        ("evaluation-1", "2"),
    }


def test_later_observations_do_not_extend_a_saved_assessment(*, session):
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

    values = records["observation"].model_dump() | {"observation_id": "later", "sequence": 2}
    session.add(models.Observation(**values))
    session.commit()
    evidence = session.exec(
        select(models.Observation)
        .join(
            models.Assessment,
            (models.Observation.case_id == models.Assessment.case_id)
            & (models.Observation.sequence <= models.Assessment.through_sequence),
        )
        .where(models.Assessment.assessment_id == records["assessment"].assessment_id)
    ).all()
    assert [row.observation_id for row in evidence] == ["chunk"]


def test_pending_assessment_accepts_one_appended_resolution(*, session):
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

    pending = models.Assessment(
        **(
            records["assessment"].model_dump()
            | {
                "assessment_id": None,
                "evaluation_id": "pending",
                "status": "pending",
                "next_due_at_us": 20,
            }
        )
    )
    session.add(pending)
    session.commit()
    resolution = records["assessment"].model_dump() | {
        "assessment_id": None,
        "evaluation_id": "resolution",
        "evaluated_at_us": 20,
        "resolves_assessment_id": pending.assessment_id,
    }
    session.add(models.Assessment(**resolution))
    session.commit()
    session.refresh(pending)
    assert pending.status == "pending"
    assert pending.next_due_at_us == 20
    session.add(models.Assessment(**(resolution | {"evaluation_id": "duplicate"})))
    with pytest.raises(IntegrityError, match="UNIQUE"):
        session.commit()


def test_finalized_assessment_cannot_be_resolved(*, session):
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

    values = records["assessment"].model_dump() | {
        "assessment_id": None,
        "evaluation_id": "resolution",
        "resolves_assessment_id": records["assessment"].assessment_id,
    }
    session.add(models.Assessment(**values))
    with pytest.raises(IntegrityError, match="matching pending assessment"):
        session.commit()
