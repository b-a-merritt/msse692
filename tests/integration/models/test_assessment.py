import pytest
from sqlalchemy import delete
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from normative_conformance import models


@pytest.mark.parametrize("operation", ["update", "delete"])
@pytest.mark.parametrize(
    "table",
    [
        models.Assessment,
        models.AssessmentActionProbability,
        models.Classification,
        models.ClassificationTopicScore,
        models.ClassificationBehaviorScore,
    ],
)
def test_retained_decisions_cannot_be_changed(session, table, operation):
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.flush()
    observation = models.Observation(
        case_id="case",
        observation_id="original",
        sequence=1,
        received_at_us=1,
        speaker_id="A",
        start_at_us=0,
        end_at_us=1,
        transcript="Please help",
        signal_level_min=-40,
        signal_level_avg=-30,
        signal_level_max=-20,
    )
    session.add_all(
        [
            observation,
            models.TargetAssignment(
                case_id="case", target_revision=1, assigned_at_us=0, speaker_id="A"
            ),
        ]
    )
    session.flush()
    assessment = models.Assessment(
        case_id="case",
        target_revision=1,
        model_id="jev-1.14.0",
        prompt_version="conversation-1",
        evaluated_at_us=2,
        completed_at_us=3,
        after_sequence=0,
        through_sequence=1,
        action="intervene",
        action_confidence=0.8,
        selection_threshold=0.7,
        request_json="{}",
    )
    session.add(assessment)
    session.flush()
    classification = models.Classification(
        assessment_id=assessment.assessment_id,
        observation_key=observation.observation_key,
        primary_topic="chores",
        intensity=1.5,
    )
    session.add(classification)
    session.flush()
    session.add_all(
        [
            models.ClassificationTopicScore(
                classification_id=classification.classification_id, topic="chores", score=0.8
            ),
            models.ClassificationBehaviorScore(
                classification_id=classification.classification_id,
                behavior="criticism",
                score=0.9,
            ),
            models.AssessmentActionProbability(
                assessment_id=assessment.assessment_id, action="intervene", probability=0.8
            ),
        ]
    )
    session.commit()
    column = (
        table.classification_id
        if table in (models.ClassificationTopicScore, models.ClassificationBehaviorScore)
        else table.assessment_id
    )
    statement = delete(table) if operation == "delete" else update(table).values({column: 99})
    with pytest.raises(IntegrityError, match="is append-only"):
        session.execute(statement)
    session.rollback()
    session.expire_all()
    assert session.get(models.Assessment, assessment.assessment_id).action == "intervene"
    assert (
        session.get(models.Classification, classification.classification_id).primary_topic
        == "chores"
    )


@pytest.mark.parametrize(
    "changes,reason",
    [
        pytest.param({"action": "invented"}, "CHECK", id="unknown-action"),
        pytest.param({"action_confidence": 1.1}, "CHECK", id="confidence-above-one"),
        pytest.param({"after_sequence": 1}, "CHECK", id="empty-range"),
        pytest.param({"through_sequence": 2}, "FOREIGN KEY", id="unstored-sequence"),
        pytest.param({"target_revision": 2}, "FOREIGN KEY", id="unassigned-target"),
        pytest.param({"request_json": "invalid"}, "CHECK", id="invalid-request"),
    ],
)
def test_assessment_integrity_constraints(session, changes, reason):
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.flush()
    session.add_all(
        [
            models.Observation(
                case_id="case",
                observation_id="one",
                sequence=1,
                received_at_us=1,
                speaker_id="A",
                start_at_us=0,
                end_at_us=1,
                transcript="Hello",
                signal_level_min=-40,
                signal_level_avg=-30,
                signal_level_max=-20,
            ),
            models.TargetAssignment(
                case_id="case", target_revision=1, assigned_at_us=0, speaker_id="A"
            ),
        ]
    )
    session.commit()
    values = {
        "case_id": "case",
        "target_revision": 1,
        "model_id": "jev-1.14.0",
        "prompt_version": "conversation-1",
        "evaluated_at_us": 2,
        "completed_at_us": 3,
        "after_sequence": 0,
        "through_sequence": 1,
        "action": "remain_silent",
        "action_confidence": 0.8,
        "selection_threshold": 0.7,
        "request_json": "{}",
    } | changes
    session.add(models.Assessment(**values))
    with pytest.raises(IntegrityError, match=reason):
        session.commit()


def test_an_observation_is_classified_once_per_assessment(session):
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.flush()
    observation = models.Observation(
        case_id="case",
        observation_id="one",
        sequence=1,
        received_at_us=1,
        speaker_id="A",
        start_at_us=0,
        end_at_us=1,
        transcript="Hello",
        signal_level_min=-40,
        signal_level_avg=-30,
        signal_level_max=-20,
    )
    session.add_all(
        [
            observation,
            models.TargetAssignment(
                case_id="case", target_revision=1, assigned_at_us=0, speaker_id="A"
            ),
        ]
    )
    session.flush()
    assessment = models.Assessment(
        case_id="case",
        target_revision=1,
        model_id="jev-1.14.0",
        prompt_version="conversation-1",
        evaluated_at_us=2,
        completed_at_us=3,
        after_sequence=0,
        through_sequence=1,
        action="remain_silent",
        action_confidence=0.8,
        selection_threshold=0.7,
        request_json="{}",
    )
    session.add(assessment)
    session.flush()
    session.add_all(
        [
            models.Classification(
                assessment_id=assessment.assessment_id,
                observation_key=observation.observation_key,
                primary_topic=topic,
                intensity=None,
            )
            for topic in ("chores", "money")
        ]
    )
    with pytest.raises(IntegrityError, match="UNIQUE"):
        session.commit()
