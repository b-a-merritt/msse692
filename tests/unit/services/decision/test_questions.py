from typesafe_sdk import Choice
from typesafe_sdk import Noul
from typesafe_sdk import Score

from normative_conformance.schemas.decision import DecisionSnapshot
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.services.decision.questions import build_questions


def test_questions_reference_explicit_rows_and_classify_only_new_speech():
    context = ObservationInput(
        case_id="case",
        observation_id="context",
        speaker_id="A",
        start_at="1970-01-01T00:00:00Z",
        end_at="1970-01-01T00:00:01Z",
        transcript="Hello",
        signal_level_min=-40,
        signal_level_avg=-30,
        signal_level_max=-20,
    )
    target = context.model_copy(update={"observation_id": "target"})
    other = context.model_copy(update={"observation_id": "other", "speaker_id": "B"})
    snapshot = DecisionSnapshot(
        case_id="case",
        target_speaker_id="A",
        target_revision=1,
        after_sequence=1,
        through_sequence=3,
        captured_at="1970-01-01T00:01:00Z",
        observations=[context, target, other],
        new_observation_ids=["target", "other"],
    )
    questions = build_questions(snapshot=snapshot)
    assert not any(key.startswith("0.") for key in questions)
    assert isinstance(questions["1.topic.chores"], Noul)
    assert "observations[1]" in questions["1.topic.chores"].instructions
    assert isinstance(questions["2.primary"], Choice)
    assert "unknown" in questions["2.primary"].criteria
    assert isinstance(questions["1.intensity"], Score)
    assert "2.intensity" not in questions
    assert not any(key.startswith("2.behavior.") for key in questions)
    assert set(questions["action"].criteria) == {
        "remain_silent",
        "await_context",
        "reflect_later",
        "intervene",
    }
    assert "apologies" in questions["action"].instructions
