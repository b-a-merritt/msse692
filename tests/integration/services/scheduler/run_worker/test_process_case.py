import json
from datetime import UTC
from datetime import datetime
from importlib import import_module

import httpx2
import pytest
from sqlmodel import select
from typesafe_sdk import RetryPolicy
from typesafe_sdk import TypeSafeClient

from normative_conformance.database import read_session
from normative_conformance.database import write_session
from normative_conformance.models.assessment import Assessment
from normative_conformance.models.assessment import Classification
from normative_conformance.models.assessment import ClassificationTopicScore
from normative_conformance.models.case import ConversationCase
from normative_conformance.models.case import TargetAssignment
from normative_conformance.models.normative_model import NormativeModel
from normative_conformance.models.normative_model import NormativeModelTopic
from normative_conformance.models.observation import Observation
from normative_conformance.models.speaker_revision import ReplacedObservation
from normative_conformance.models.speaker_revision import SpeakerRevision
from normative_conformance.schemas.decision import DecisionAnswers
from normative_conformance.schemas.decision import ObservationAnswers
from normative_conformance.services.assessment.list_assessment_records import (
    list_assessment_records,
)

module = import_module("normative_conformance.services.scheduler.run_worker.process_case")


@pytest.mark.parametrize(
    "in_flight_speakers,handled_through",
    [
        pytest.param([], 2, id="same-target"),
        pytest.param(["A"], 1, id="target-changed-during-call"),
    ],
)
def test_saves_the_target_turn_as_first_labeled_and_advances_only_its_current_target(
    engine, session, monkeypatch, in_flight_speakers, handled_through
):
    session.add(
        ConversationCase(
            case_id="case",
            created_at_us=0,
            last_handled_sequence=1,
            last_handled_target_revision=1,
        )
    )
    session.flush()
    originals = {
        identity: Observation(
            case_id="case",
            observation_id=identity,
            sequence=sequence,
            start_at_us=sequence * 1_000_000,
            end_at_us=sequence * 1_000_000 + 500_000,
            received_at_us=sequence * 1_000_000,
            speaker_id=speaker,
            transcript=transcript,
            signal_level_min=-40,
            signal_level_avg=-30,
            signal_level_max=-20,
        )
        for identity, sequence, speaker, transcript in [
            ("one", 1, "A", "Hello"),
            ("two", 2, "B", "Please help"),
            ("three", 3, "A", "Sure"),
        ]
    }
    revision = SpeakerRevision(case_id="case", received_at_us=3_000_000)
    session.add_all(
        [
            *originals.values(),
            revision,
            TargetAssignment(case_id="case", target_revision=1, assigned_at_us=0, speaker_id="B"),
        ]
    )
    session.flush()
    # A correction relabels the target's turn; decisions still use the first label.
    session.add_all(
        [
            Observation(
                case_id="case",
                observation_id="two-A",
                speaker_revision_id=revision.speaker_revision_id,
                start_at_us=2_000_000,
                end_at_us=2_500_000,
                speaker_id="A",
                transcript="Please help",
                signal_level_min=-40,
                signal_level_avg=-30,
                signal_level_max=-20,
            ),
            ReplacedObservation(
                speaker_revision_id=revision.speaker_revision_id,
                observation_key=originals["two"].observation_key,
            ),
        ]
    )
    session.commit()
    captured = []

    def ask(*, snapshot, evidence, client):
        captured.append(snapshot)
        assert [(row.observation_id, row.speaker_id) for row in snapshot.observations] == [
            ("one", "A"),
            ("two", "B"),
        ]
        assert snapshot.new_observation_ids == ["two"]
        assert snapshot.target_speaker_id == "B"
        # This independent writer succeeds while the provider is in flight.
        with write_session(engine=engine) as writer:
            writer.add_all(
                [
                    TargetAssignment(
                        case_id="case", target_revision=2, assigned_at_us=4, speaker_id=speaker
                    )
                    for speaker in in_flight_speakers
                ]
            )
            writer.commit()
        result = DecisionAnswers(
            model="jev-1.14.0",
            prompt_version="conversation-1",
            observations=[
                ObservationAnswers(
                    observation_id="two",
                    topic_scores={"chores": 0.8, "money": 0.1},
                    primary_topic="chores",
                    behavior_scores={},
                    intensity=None,
                )
            ],
            action="await_context",
            action_probabilities={"await_context": 1.0},
            action_confidence=1.0,
        )
        return (
            result,
            json.dumps({"state": snapshot.model_dump(mode="json")}),
        )

    monkeypatch.setattr(module.jev, "evaluate", ask)
    assessment_id = module.process_case(
        case_id="case",
        max_batch_seconds=60,
        idle_seconds=20,
        context_seconds=30,
        engine=engine,
        client=object(),
        now=lambda: datetime(1970, 1, 1, second=4, tzinfo=UTC),
    )
    with read_session(engine=engine) as check:
        rows = check.exec(select(Assessment)).all()
        assert len(rows) == 1
        assert rows[0].assessment_id == assessment_id
        assert rows[0].target_revision == 1
        assert (rows[0].after_sequence, rows[0].through_sequence) == (1, 2)
        state = json.loads(rows[0].request_json)["state"]
        assert state == captured[0].model_dump(mode="json")
        assert check.exec(select(Classification.observation_key)).all() == [
            originals["two"].observation_key
        ]
        case = check.get(ConversationCase, "case")
        assert case.last_handled_sequence == handled_through
        assert case.last_handled_target_revision == 1
        [record] = list_assessment_records(case_id="case", session=check)
        assert record.action == "await_context"
        assert record.observations[0].observation_id == "two"
        assert record.observations[0].topic_scores == {"chores": 0.8, "money": 0.1}
        assert record.observations[0].topics == ["chores"]
        assert record.observations[0].primary_topic == "chores"
        assert record.target_speaker_id == "B"


def test_earlier_classifications_matching_the_newest_model_send_evidence(
    engine, session, monkeypatch
):
    session.add(
        ConversationCase(
            case_id="case",
            created_at_us=0,
            last_handled_sequence=1,
            last_handled_target_revision=1,
        )
    )
    session.flush()
    speech = {
        identity: Observation(
            case_id="case",
            observation_id=identity,
            sequence=sequence,
            start_at_us=sequence * 1_000_000,
            end_at_us=sequence * 1_000_000 + 500_000,
            received_at_us=sequence * 1_000_000,
            speaker_id=speaker,
            transcript=transcript,
            signal_level_min=-40,
            signal_level_avg=-30,
            signal_level_max=-20,
        )
        for identity, sequence, speaker, transcript in [
            ("one", 1, "A", "My mom wants six hundred from our savings."),
            ("two", 2, "B", "Of course she does."),
            ("three", 3, "A", "Please."),
        ]
    }
    model = NormativeModel(discovered_at_us=0)
    session.add_all(
        [
            *speech.values(),
            TargetAssignment(case_id="case", target_revision=1, assigned_at_us=0, speaker_id="B"),
            model,
        ]
    )
    session.flush()
    # The earlier batch covered both required topics.
    earlier = Assessment(
        case_id="case",
        target_revision=1,
        model_id="jev-1.14.0",
        prompt_version="conversation-3",
        evaluated_at_us=1,
        completed_at_us=1,
        after_sequence=0,
        through_sequence=1,
        selection_threshold=0.7,
        request_json="{}",
    )
    session.add_all(
        [earlier]
        + [
            NormativeModelTopic(normative_model_id=model.normative_model_id, topic=topic)
            for topic in ["budgeting", "extended_family"]
        ]
    )
    session.flush()
    classification = Classification(
        assessment_id=earlier.assessment_id,
        observation_key=speech["one"].observation_key,
        primary_topic="budgeting",
        intensity=None,
    )
    session.add(classification)
    session.flush()
    session.add_all(
        [
            ClassificationTopicScore(
                classification_id=classification.classification_id, topic=topic, score=0.9
            )
            for topic in ["budgeting", "extended_family"]
        ]
    )
    session.commit()
    requests = []

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        # Neutral answers; only keys and option labels are copied from the request.
        answers = {}
        for key, question in payload["questions"].items():
            if question["type"] == "noul":
                answers[key] = {"type": "noul", "noul": 0.1}
            elif question["type"] == "choice":
                choice = "await_context" if key == "action" else "unknown"
                answers[key] = {
                    "type": "choice",
                    "choice": choice,
                    "confidence": 1.0,
                    "probabilities": {
                        option: 1.0 if option == choice else 0.0 for option in question["criteria"]
                    },
                }
            else:
                answers[key] = {
                    "type": "score",
                    "score": 0.0,
                    "confidence": 1.0,
                    "legend": {str(i): level for i, level in enumerate(question["criteria"])},
                    "probabilities": {"0": 1.0, "1": 0.0, "2": 0.0, "3": 0.0},
                }
        return httpx2.Response(200, json={"model": "jev-1.14.0", "answers": answers, "usage": {}})

    with TypeSafeClient(
        api_key="integration-key",
        transport=httpx2.MockTransport(respond),
        base_url="https://api.typesafe.ai",
        compression=False,
        retry=RetryPolicy(max_retries=0),
    ) as client:
        assessment_id = module.process_case(
            case_id="case",
            max_batch_seconds=60,
            idle_seconds=20,
            context_seconds=30,
            engine=engine,
            client=client,
            now=lambda: datetime(1970, 1, 1, second=4, tzinfo=UTC),
        )

    # Only the action question was told about the evidence, and the stored request records it.
    [payload] = requests
    assert "budgeting, extended family" in payload["questions"]["action"]["instructions"]
    assert "evidence" not in payload["state"]
    with read_session(engine=engine) as check:
        stored = check.get(Assessment, assessment_id)
        assert json.loads(stored.request_json)["evidence"] == {
            "normative_model_id": model.normative_model_id,
            "topics": ["budgeting", "extended_family"],
        }
