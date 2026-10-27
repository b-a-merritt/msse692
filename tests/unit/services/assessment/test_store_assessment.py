from datetime import datetime
from datetime import timezone
from unittest.mock import Mock

from sqlmodel import Session

from normative_conformance.models.assessment import Assessment
from normative_conformance.models.assessment import AssessmentActionProbability
from normative_conformance.models.assessment import Classification
from normative_conformance.models.assessment import ClassificationBehaviorScore
from normative_conformance.models.assessment import ClassificationTopicScore
from normative_conformance.schemas.decision import DecisionAnswers
from normative_conformance.schemas.decision import DecisionSnapshot
from normative_conformance.schemas.decision import ObservationAnswers
from normative_conformance.services.assessment.store_assessment import store_assessment


def test_stores_decisions_as_queryable_rows_without_committing():
    session = Mock(spec=Session)
    added = []

    session.add.side_effect = added.append

    # The database assigns IDs when rows are flushed.
    def flush():
        for row in added:
            if isinstance(row, Assessment):
                row.assessment_id = 7
            if isinstance(row, Classification):
                row.classification_id = 11

    session.flush.side_effect = flush
    session.add_all.side_effect = lambda rows: added.extend(rows)
    snapshot = DecisionSnapshot(
        case_id="case",
        target_speaker_id="B",
        target_revision=2,
        after_sequence=3,
        through_sequence=4,
        captured_at=datetime(1970, 1, 1, microsecond=10, tzinfo=timezone.utc),
        observations=[],
        new_observation_ids=["revised"],
    )
    result = DecisionAnswers(
        model="jev-1.14.0",
        prompt_version="conversation-1",
        observations=[
            ObservationAnswers(
                observation_id="revised",
                topic_scores={"chores": 0.8},
                primary_topic="chores",
                behavior_scores={"criticism": 0.9},
                intensity=1.5,
            )
        ],
        action="reflect_later",
        action_confidence=0.8,
        action_probabilities={"reflect_later": 0.8, "intervene": 0.2},
    )
    assessment = store_assessment(
        session=session,
        snapshot=snapshot,
        answers=result,
        request_json='{"state":{}}',
        observation_keys={"revised": 5, "unused": 6},
        completed_at_us=20,
    )
    assert assessment.action == "reflect_later"
    assert assessment.target_revision == 2
    assert (assessment.after_sequence, assessment.through_sequence) == (3, 4)
    assert (assessment.evaluated_at_us, assessment.completed_at_us) == (10, 20)
    assert assessment.model_id == "jev-1.14.0"
    assert assessment.request_json == '{"state":{}}'
    assert [r.model_dump() for r in added if isinstance(r, Classification)] == [
        {
            "classification_id": 11,
            "assessment_id": 7,
            "observation_key": 5,
            "primary_topic": "chores",
            "intensity": 1.5,
        }
    ]
    assert [r.model_dump() for r in added if isinstance(r, ClassificationTopicScore)] == [
        {"classification_id": 11, "topic": "chores", "score": 0.8}
    ]
    assert [r.model_dump() for r in added if isinstance(r, ClassificationBehaviorScore)] == [
        {"classification_id": 11, "behavior": "criticism", "score": 0.9}
    ]
    assert {
        r.action: r.probability for r in added if isinstance(r, AssessmentActionProbability)
    } == {
        "reflect_later": 0.8,
        "intervene": 0.2,
    }
    session.commit.assert_not_called()
