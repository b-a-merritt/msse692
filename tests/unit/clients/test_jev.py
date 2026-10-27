import json
from unittest.mock import Mock

from typesafe_sdk import Noul
from typesafe_sdk import TypeSafeClient

from normative_conformance.clients import jev
from normative_conformance.schemas.decision import DecisionSnapshot
from normative_conformance.schemas.observation import ObservationInput


def test_sends_snapshot_and_questions_then_reads_answers_and_returns_the_request(monkeypatch):
    snapshot = DecisionSnapshot(
        case_id="case",
        target_speaker_id="A",
        target_revision=1,
        after_sequence=0,
        through_sequence=1,
        captured_at="1970-01-01T00:01:00Z",
        observations=[
            ObservationInput(
                case_id="case",
                observation_id="one",
                speaker_id="A",
                start_at="1970-01-01T00:00:00Z",
                end_at="1970-01-01T00:00:01Z",
                transcript="Please help",
                signal_level_min=-40,
                signal_level_avg=-30,
                signal_level_max=-20,
            )
        ],
        new_observation_ids=["one"],
    )
    questions = {"0.topic.chores": Noul(instructions="Is this about chores?")}
    monkeypatch.setattr(jev, "build_questions", Mock(return_value=questions))
    answers = object()
    read_answers = Mock(return_value=answers)
    monkeypatch.setattr(jev, "read_answers", read_answers)
    client = Mock(spec=TypeSafeClient)

    result, request = jev.evaluate(snapshot=snapshot, client=client)

    state = snapshot.model_dump(mode="json")
    client.system_one.assert_called_once_with(model="jev-1.14.0", state=state, questions=questions)
    read_answers.assert_called_once_with(
        snapshot=snapshot, questions=questions, response=client.system_one.return_value
    )
    assert result is answers
    assert json.loads(request) == {
        "model": "jev-1.14.0",
        "state": state,
        "questions": {"0.topic.chores": {"type": "noul", "instructions": "Is this about chores?"}},
    }
