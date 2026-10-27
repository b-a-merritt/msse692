from unittest.mock import MagicMock
from unittest.mock import Mock

from sqlmodel import Session

from normative_conformance import models
from normative_conformance.services.assessment.list_assessment_records import (
    list_assessment_records,
)


def test_reads_structured_decisions_and_applies_the_stored_threshold():
    records = {
        models.Assessment: [
            (
                models.Assessment(
                    assessment_id=7,
                    case_id="case",
                    target_revision=2,
                    model_id="jev-1.14.0",
                    prompt_version="conversation-1",
                    evaluated_at_us=10,
                    completed_at_us=20,
                    after_sequence=3,
                    through_sequence=4,
                    action="reflect_later",
                    action_confidence=0.8,
                    selection_threshold=0.7,
                    request_json="{}",
                ),
                "B",
            )
        ],
        models.AssessmentActionProbability: [
            models.AssessmentActionProbability(
                assessment_id=7, action="reflect_later", probability=1
            )
        ],
        models.Classification: [
            (
                models.Classification(
                    classification_id=1,
                    assessment_id=7,
                    observation_key=10,
                    primary_topic="chores",
                    intensity=1.5,
                ),
                "revised",
            ),
            (
                models.Classification(
                    classification_id=2,
                    assessment_id=7,
                    observation_key=11,
                    primary_topic="money",
                    intensity=None,
                ),
                "other",
            ),
        ],
        models.ClassificationTopicScore: [
            models.ClassificationTopicScore(classification_id=1, topic="chores", score=0.7),
            models.ClassificationTopicScore(classification_id=1, topic="money", score=0.2),
            models.ClassificationTopicScore(classification_id=2, topic="money", score=0.6),
        ],
        models.ClassificationBehaviorScore: [
            models.ClassificationBehaviorScore(
                classification_id=1, behavior="criticism", score=0.9
            ),
            models.ClassificationBehaviorScore(classification_id=1, behavior="swearing", score=0.1),
        ],
    }
    session = Mock(spec=Session)

    def execute(query):
        values = records[query.column_descriptions[0]["entity"]]
        result = MagicMock()
        result.all.return_value = values
        result.__iter__.return_value = iter(values)
        return result

    session.exec.side_effect = execute
    [assessment] = list_assessment_records(case_id="case", session=session)
    assert assessment.subject_speaker_id == "B"
    assert assessment.action == "reflect_later"
    assert assessment.action_probabilities == {"reflect_later": 1}
    assert assessment.target_revision == 2
    assert assessment.after_sequence == 3
    revised, other = assessment.observations
    assert revised.observation_id == "revised"
    assert revised.topics == ["chores"]
    assert revised.primary_topic == "chores"
    assert revised.behaviors == ["criticism"]
    assert revised.topic_scores == {"chores": 0.7, "money": 0.2}
    assert revised.intensity == 1.5
    # A primary topic below the threshold is reported as unknown.
    assert other.topics == other.behaviors == []
    assert other.primary_topic == "unknown"
    assert other.intensity is None
    for model in records:
        records[model] = []
    assert list_assessment_records(case_id="missing", session=session) == []
