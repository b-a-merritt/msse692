from datetime import UTC
from datetime import datetime

from sqlmodel import select

from normative_conformance.database import write_session
from normative_conformance.models.assessment import Assessment
from normative_conformance.models.assessment import AssessmentActionProbability
from normative_conformance.models.assessment import Classification
from normative_conformance.models.assessment import ClassificationTopicScore
from normative_conformance.models.observation import Observation


def test_lists_structured_decisions_for_the_requested_case(open_client):
    now = datetime(1970, 1, 1, minute=1, tzinfo=UTC)
    with open_client(now=lambda: now) as client:
        assert (
            client.put("/api/v1/cases/case/target", json={"target_speaker_id": "A"}).status_code
            == 200
        )
        assert (
            client.post(
                "/api/v1/observations",
                json={
                    "case_id": "case",
                    "observation_id": "one",
                    "speaker_id": "A",
                    "start_at": "1970-01-01T00:00:01Z",
                    "end_at": "1970-01-01T00:00:02Z",
                    "transcript": "Please help",
                    "signal_level_min": -40,
                    "signal_level_avg": -30,
                    "signal_level_max": -20,
                },
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/api/v1/observations",
                json={
                    "case_id": "case",
                    "observation_id": "two",
                    "speaker_id": "A",
                    "start_at": "1970-01-01T00:00:02Z",
                    "end_at": "1970-01-01T00:00:03Z",
                    "transcript": "with this",
                    "signal_level_min": -40,
                    "signal_level_avg": -30,
                    "signal_level_max": -20,
                },
            ).status_code
            == 201
        )
        with write_session(engine=client.app.state.engine) as session:
            observation_key = session.exec(
                select(Observation.observation_key).where(Observation.observation_id == "one")
            ).one()
            assessment = Assessment(
                case_id="case",
                target_revision=1,
                model_id="jev-1.14.0",
                prompt_version="conversation-1",
                evaluated_at_us=3_000_000,
                completed_at_us=4_000_000,
                after_sequence=0,
                through_sequence=2,
                action="remain_silent",
                action_confidence=0.9,
                selection_threshold=0.7,
                request_json='{"state":{}}',
            )
            session.add(assessment)
            session.flush()
            classification = Classification(
                assessment_id=assessment.assessment_id,
                observation_key=observation_key,
                primary_topic="chores",
                intensity=0,
            )
            session.add(classification)
            session.flush()
            session.add(
                ClassificationTopicScore(
                    classification_id=classification.classification_id, topic="chores", score=0.8
                )
            )
            session.add(
                AssessmentActionProbability(
                    assessment_id=assessment.assessment_id, action="remain_silent", probability=1
                )
            )
            session.commit()
        response = client.get("/api/v1/cases/case/assessments")
        assert response.status_code == 200
        [record] = response.json()["items"]
        assert record["action"] == "remain_silent"
        assert record["model"] == "jev-1.14.0"
        assert record["target_speaker_id"] == "A"
        assert record["action_probabilities"] == {"remain_silent": 1}
        assert record["observations"] == [
            {
                "observation_id": "one",
                # The classification covers the target's whole turn.
                "observation_ids": ["one", "two"],
                "topic_scores": {"chores": 0.8},
                "topics": ["chores"],
                "primary_topic": "chores",
                "behavior_scores": {},
                "behaviors": [],
                "intensity": 0,
            }
        ]
        assert record["after_sequence"] == 0
        assert record["through_sequence"] == 2
        assert record["evaluated_at"] == "1970-01-01T00:00:03Z"
        assert record["completed_at"] == "1970-01-01T00:00:04Z"
        assert "request_json" not in record
        assert client.get("/api/v1/cases/missing/assessments").json() == {"items": []}
