"""Intervention persistence, eligible sources, and delivery timestamps."""

import pytest
from sqlalchemy.exc import IntegrityError

from normative_conformance import models


@pytest.mark.parametrize(
    ("action", "accepted"),
    [
        pytest.param("intervene", True, id="intervene"),
        pytest.param("remain_silent", False, id="remain-silent"),
        pytest.param("await_context", False, id="await-context"),
        pytest.param("reflect_later", False, id="reflect-later"),
    ],
)
def test_only_intervene_assessments_can_be_sources(*, session, action, accepted):
    session.add(models.CaseLog(case_id="case", created_at_us=1))
    session.flush()
    session.add_all(
        [
            models.Observation(
                case_id="case",
                observation_id="chunk",
                sequence=1,
                received_at_us=10,
                speaker_id="A",
                start_at_us=1,
                end_at_us=9,
                transcript="Hello",
                signal_level_min=-30.0,
                signal_level_avg=-20.0,
                signal_level_max=-10.0,
            ),
            models.TargetAssignment(
                case_id="case", target_revision=1, assigned_at_us=1, speaker_id="A"
            ),
        ]
    )
    session.flush()
    assessment = models.Assessment(
        case_id="case",
        target_revision=1,
        model_id="jev-1.14.0",
        prompt_version="conversation-1",
        evaluated_at_us=11,
        completed_at_us=11,
        after_sequence=0,
        through_sequence=1,
        action=action,
        action_confidence=0.9,
        selection_threshold=0.7,
        request_json="{}",
    )
    session.add(assessment)
    session.flush()
    session.add(
        models.Intervention(
            assessment_id=assessment.assessment_id, message="Feedback", created_at_us=12
        )
    )
    if accepted:
        session.commit()
    else:
        with pytest.raises(IntegrityError, match="intervene assessment"):
            session.commit()


@pytest.mark.parametrize(
    ("changes", "constraint"),
    [
        pytest.param({"assessment_id": 99}, "intervene assessment", id="missing-assessment"),
        pytest.param({"intervention_id": 0}, "CHECK", id="nonpositive-id"),
        pytest.param({}, "UNIQUE", id="second-intervention-for-assessment"),
    ],
)
def test_invalid_interventions_are_rejected(*, session, changes, constraint):
    session.add(models.CaseLog(case_id="case", created_at_us=1))
    session.flush()
    session.add_all(
        [
            models.Observation(
                case_id="case",
                observation_id="chunk",
                sequence=1,
                received_at_us=10,
                speaker_id="A",
                start_at_us=1,
                end_at_us=9,
                transcript="Hello",
                signal_level_min=-30.0,
                signal_level_avg=-20.0,
                signal_level_max=-10.0,
            ),
            models.TargetAssignment(
                case_id="case", target_revision=1, assigned_at_us=1, speaker_id="A"
            ),
        ]
    )
    session.flush()
    assessment = models.Assessment(
        case_id="case",
        target_revision=1,
        model_id="jev-1.14.0",
        prompt_version="conversation-1",
        evaluated_at_us=11,
        completed_at_us=11,
        after_sequence=0,
        through_sequence=1,
        action="intervene",
        action_confidence=0.9,
        selection_threshold=0.7,
        request_json="{}",
    )
    session.add(assessment)
    session.flush()
    intervention = models.Intervention(
        assessment_id=assessment.assessment_id, message="Feedback", created_at_us=12
    )
    session.add(intervention)
    session.commit()

    values = {"assessment_id": assessment.assessment_id, "message": "Other", "created_at_us": 12}
    session.add(models.Intervention(**(values | changes)))
    with pytest.raises(IntegrityError, match=constraint):
        session.commit()


@pytest.mark.parametrize("sent_at_us", [12, 13])
def test_intervention_can_be_marked_sent(*, session, sent_at_us):
    session.add(models.CaseLog(case_id="case", created_at_us=1))
    session.flush()
    session.add_all(
        [
            models.Observation(
                case_id="case",
                observation_id="chunk",
                sequence=1,
                received_at_us=10,
                speaker_id="A",
                start_at_us=1,
                end_at_us=9,
                transcript="Hello",
                signal_level_min=-30.0,
                signal_level_avg=-20.0,
                signal_level_max=-10.0,
            ),
            models.TargetAssignment(
                case_id="case", target_revision=1, assigned_at_us=1, speaker_id="A"
            ),
        ]
    )
    session.flush()
    assessment = models.Assessment(
        case_id="case",
        target_revision=1,
        model_id="jev-1.14.0",
        prompt_version="conversation-1",
        evaluated_at_us=11,
        completed_at_us=11,
        after_sequence=0,
        through_sequence=1,
        action="intervene",
        action_confidence=0.9,
        selection_threshold=0.7,
        request_json="{}",
    )
    session.add(assessment)
    session.flush()
    intervention = models.Intervention(
        assessment_id=assessment.assessment_id, message="Feedback", created_at_us=12
    )
    session.add(intervention)
    session.commit()

    intervention.sent_at_us = sent_at_us
    session.commit()
    session.refresh(intervention)
    assert intervention.sent_at_us == sent_at_us


def test_intervention_cannot_be_sent_before_creation(*, session):
    session.add(models.CaseLog(case_id="case", created_at_us=1))
    session.flush()
    session.add_all(
        [
            models.Observation(
                case_id="case",
                observation_id="chunk",
                sequence=1,
                received_at_us=10,
                speaker_id="A",
                start_at_us=1,
                end_at_us=9,
                transcript="Hello",
                signal_level_min=-30.0,
                signal_level_avg=-20.0,
                signal_level_max=-10.0,
            ),
            models.TargetAssignment(
                case_id="case", target_revision=1, assigned_at_us=1, speaker_id="A"
            ),
        ]
    )
    session.flush()
    assessment = models.Assessment(
        case_id="case",
        target_revision=1,
        model_id="jev-1.14.0",
        prompt_version="conversation-1",
        evaluated_at_us=11,
        completed_at_us=11,
        after_sequence=0,
        through_sequence=1,
        action="intervene",
        action_confidence=0.9,
        selection_threshold=0.7,
        request_json="{}",
    )
    session.add(assessment)
    session.flush()
    intervention = models.Intervention(
        assessment_id=assessment.assessment_id, message="Feedback", created_at_us=12
    )
    session.add(intervention)
    session.commit()

    intervention.sent_at_us = 11
    with pytest.raises(IntegrityError, match="CHECK constraint failed"):
        session.commit()
    session.rollback()
    session.refresh(intervention)
    assert intervention.sent_at_us is None


@pytest.mark.parametrize(
    "sent_at_us",
    [
        pytest.param(14, id="resent"),
        pytest.param(None, id="unsent"),
    ],
)
def test_intervention_is_marked_sent_only_once(*, session, sent_at_us):
    session.add(models.CaseLog(case_id="case", created_at_us=1))
    session.flush()
    session.add_all(
        [
            models.Observation(
                case_id="case",
                observation_id="chunk",
                sequence=1,
                received_at_us=10,
                speaker_id="A",
                start_at_us=1,
                end_at_us=9,
                transcript="Hello",
                signal_level_min=-30.0,
                signal_level_avg=-20.0,
                signal_level_max=-10.0,
            ),
            models.TargetAssignment(
                case_id="case", target_revision=1, assigned_at_us=1, speaker_id="A"
            ),
        ]
    )
    session.flush()
    assessment = models.Assessment(
        case_id="case",
        target_revision=1,
        model_id="jev-1.14.0",
        prompt_version="conversation-1",
        evaluated_at_us=11,
        completed_at_us=11,
        after_sequence=0,
        through_sequence=1,
        action="intervene",
        action_confidence=0.9,
        selection_threshold=0.7,
        request_json="{}",
    )
    session.add(assessment)
    session.flush()
    intervention = models.Intervention(
        assessment_id=assessment.assessment_id, message="Feedback", created_at_us=12
    )
    session.add(intervention)
    session.commit()

    intervention.sent_at_us = 13
    session.commit()
    intervention.sent_at_us = sent_at_us
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
    session.add(models.CaseLog(case_id="case", created_at_us=1))
    session.flush()
    session.add_all(
        [
            models.Observation(
                case_id="case",
                observation_id="chunk",
                sequence=1,
                received_at_us=10,
                speaker_id="A",
                start_at_us=1,
                end_at_us=9,
                transcript="Hello",
                signal_level_min=-30.0,
                signal_level_avg=-20.0,
                signal_level_max=-10.0,
            ),
            models.TargetAssignment(
                case_id="case", target_revision=1, assigned_at_us=1, speaker_id="A"
            ),
        ]
    )
    session.flush()
    assessment = models.Assessment(
        case_id="case",
        target_revision=1,
        model_id="jev-1.14.0",
        prompt_version="conversation-1",
        evaluated_at_us=11,
        completed_at_us=11,
        after_sequence=0,
        through_sequence=1,
        action="intervene",
        action_confidence=0.9,
        selection_threshold=0.7,
        request_json="{}",
    )
    session.add(assessment)
    session.flush()
    intervention = models.Intervention(
        assessment_id=assessment.assessment_id, message="Feedback", created_at_us=12
    )
    session.add(intervention)
    session.commit()

    for name, value in changes.items():
        setattr(intervention, name, value)
    intervention.sent_at_us = 13
    with pytest.raises(IntegrityError, match="marked sent once"):
        session.commit()


def test_intervention_is_retained(*, session):
    session.add(models.CaseLog(case_id="case", created_at_us=1))
    session.flush()
    session.add_all(
        [
            models.Observation(
                case_id="case",
                observation_id="chunk",
                sequence=1,
                received_at_us=10,
                speaker_id="A",
                start_at_us=1,
                end_at_us=9,
                transcript="Hello",
                signal_level_min=-30.0,
                signal_level_avg=-20.0,
                signal_level_max=-10.0,
            ),
            models.TargetAssignment(
                case_id="case", target_revision=1, assigned_at_us=1, speaker_id="A"
            ),
        ]
    )
    session.flush()
    assessment = models.Assessment(
        case_id="case",
        target_revision=1,
        model_id="jev-1.14.0",
        prompt_version="conversation-1",
        evaluated_at_us=11,
        completed_at_us=11,
        after_sequence=0,
        through_sequence=1,
        action="intervene",
        action_confidence=0.9,
        selection_threshold=0.7,
        request_json="{}",
    )
    session.add(assessment)
    session.flush()
    intervention = models.Intervention(
        assessment_id=assessment.assessment_id, message="Feedback", created_at_us=12
    )
    session.add(intervention)
    session.commit()

    session.delete(intervention)
    with pytest.raises(IntegrityError, match="intervention is retained"):
        session.commit()
