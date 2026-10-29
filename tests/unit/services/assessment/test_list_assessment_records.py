from datetime import UTC
from datetime import datetime
from importlib import import_module
from unittest.mock import MagicMock
from unittest.mock import Mock

from sqlmodel import Session

from normative_conformance import models
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.services.observation.load_case_speech import IngestedObservation

module = import_module("normative_conformance.services.assessment.list_assessment_records")


def ingested(*, sequence, observation_id, speaker_id, second):
    return IngestedObservation(
        observation_key=sequence,
        sequence=sequence,
        received_at=datetime(1970, 1, 1, tzinfo=UTC),
        observation=ObservationInput(
            case_id="case",
            observation_id=observation_id,
            speaker_id=speaker_id,
            start_at=datetime(1970, 1, 1, second=second, tzinfo=UTC),
            end_at=datetime(1970, 1, 1, second=second + 1, tzinfo=UTC),
            transcript="Hello",
            signal_level_min=-40,
            signal_level_avg=-30,
            signal_level_max=-20,
        ),
    )


def test_reads_structured_decisions_and_applies_the_stored_threshold(monkeypatch):
    records = {
        models.Assessment: [
            models.Assessment(
                assessment_id=7,
                case_id="case",
                target_revision=2,
                model_id="jev-1.14.0",
                prompt_version="conversation-1",
                evaluated_at_us=10,
                completed_at_us=20,
                after_sequence=3,
                through_sequence=6,
                action="reflect_later",
                action_confidence=0.8,
                selection_threshold=0.7,
                request_json="{}",
            )
        ],
        models.AssessmentActionProbability: [(7, "reflect_later", 1)],
        # Observation keys 4 and 6 are the "revised" and "other" speech below.
        models.Classification: [
            models.Classification(
                classification_id=1,
                assessment_id=7,
                observation_key=4,
                primary_topic="chores",
                intensity=1.5,
            ),
            models.Classification(
                classification_id=2,
                assessment_id=7,
                observation_key=6,
                primary_topic="money",
                intensity=None,
            ),
        ],
        # Score queries select (owner ID, name, score) columns.
        models.ClassificationTopicScore: [(1, "chores", 0.7), (1, "money", 0.2), (2, "money", 0.6)],
        models.ClassificationBehaviorScore: [(1, "criticism", 0.9), (1, "swearing", 0.1)],
    }
    session = Mock(spec=Session)

    def execute(query):
        values = records[query.column_descriptions[0]["entity"]]
        result = MagicMock()
        result.all.return_value = values
        result.__iter__.return_value = iter(values)
        return result

    session.exec.side_effect = execute
    speech = [
        ingested(sequence=3, observation_id="earlier", speaker_id="A", second=0),
        ingested(sequence=4, observation_id="revised", speaker_id="A", second=1),
        ingested(sequence=5, observation_id="continued", speaker_id="A", second=2),
        ingested(sequence=6, observation_id="other", speaker_id="B", second=3),
    ]
    monkeypatch.setattr(module, "load_case_speech", Mock(return_value=speech))
    monkeypatch.setattr(module, "list_targets", Mock(return_value={2: "B"}))
    [assessment] = module.list_assessment_records(case_id="case", session=session)
    assert assessment.target_speaker_id == "B"
    assert assessment.action == "reflect_later"
    assert assessment.action_probabilities == {"reflect_later": 1}
    assert assessment.target_revision == 2
    assert assessment.after_sequence == 3
    revised, other = assessment.observations
    assert revised.observation_id == "revised"
    # Turns come from the assessment's sequence range, so earlier speech is not included.
    assert revised.observation_ids == ["revised", "continued"]
    assert other.observation_ids == ["other"]
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
    assert module.list_assessment_records(case_id="missing", session=session) == []
