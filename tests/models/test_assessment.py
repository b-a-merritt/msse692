"""Assessment persistence, model references, and saved evidence extents."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from normative_conformance import models


def test_assessment_round_trip_with_defaults_and_generated_id(*, session, records):
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
def test_invalid_assessments_are_rejected(*, session, records, changes, constraint):
    values = records["assessment"].model_dump()
    values.update(assessment_id=None, evaluation_id="evaluation-2")
    values.update(changes)
    session.add(models.Assessment(**values))
    with pytest.raises(IntegrityError, match=constraint):
        session.commit()


@pytest.mark.parametrize("status", ["conformant", "non-conformant", "pending", "conflicted"])
def test_new_evaluations_accept_all_statuses(*, session, records, status):
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


def test_evaluation_can_include_multiple_model_versions(*, session, records):
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


def test_later_observations_do_not_extend_a_saved_assessment(*, session, records):
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
