from typesafe_sdk import Choice
from typesafe_sdk import Noul
from typesafe_sdk import Score
from typesafe_sdk import SystemOneResponse

from normative_conformance.schemas.decision import DecisionSnapshot
from normative_conformance.schemas.decision import ObservationAnswers
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.services.decision import answers as module


def test_reads_raw_answers_for_only_the_questions_that_were_asked(monkeypatch):
    monkeypatch.setattr(module, "TOPICS", ("chores",))
    monkeypatch.setattr(module, "BEHAVIOR_QUESTIONS", {"swearing": "Is there profanity?"})
    row = ObservationInput(
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
    snapshot = DecisionSnapshot(
        case_id="case",
        target_speaker_id="A",
        target_revision=1,
        after_sequence=1,
        through_sequence=3,
        captured_at="1970-01-01T00:01:00Z",
        observations=[
            row,
            row.model_copy(update={"observation_id": "target"}),
            row.model_copy(update={"observation_id": "other", "speaker_id": "B"}),
        ],
        new_observation_ids=["target", "other"],
    )
    # Context (index 0) was not asked about, and only the target (index 1) had behavior questions.
    topic = Noul(instructions="Topic?")
    primary = Choice(instructions="Primary?", criteria={"chores": "Chores"})
    questions = {
        "1.topic.chores": topic,
        "1.primary": primary,
        "1.behavior.swearing": Noul(instructions="Swearing?"),
        "1.intensity": Score(instructions="Hostility?", criteria=["Civil", "Hostile"]),
        "2.topic.chores": topic,
        "2.primary": primary,
        "action": Choice(instructions="Action?", criteria={"intervene": "Prompt now"}),
    }

    def choice(name, probability):
        return {
            "type": "choice",
            "choice": name,
            "confidence": 0.6,
            "probabilities": {name: probability},
        }

    response = SystemOneResponse.model_validate(
        {
            "model": "jev-1.14.0",
            "answers": {
                "1.topic.chores": {"type": "noul", "noul": 0.2},
                "1.primary": choice("chores", 0.9),
                "1.behavior.swearing": {"type": "noul", "noul": 0.8},
                "1.intensity": {
                    "type": "score",
                    "score": 1.5,
                    "confidence": 0.5,
                    "legend": {0: "Civil", 1: "Hostile"},
                    "probabilities": {0: 0.5, 1: 0.5},
                },
                "2.topic.chores": {"type": "noul", "noul": 0.9},
                "2.primary": choice("chores", 0.8),
                "action": choice("intervene", 0.7),
            },
            "usage": {"input_tokens": 100, "output_tokens": 10},
        }
    )

    result = module.read_answers(snapshot=snapshot, questions=questions, response=response)

    assert result.observations == [
        # A weakly scored primary topic is still reported as the model's raw choice.
        ObservationAnswers(
            observation_id="target",
            topic_scores={"chores": 0.2},
            primary_topic="chores",
            behavior_scores={"swearing": 0.8},
            intensity=1.5,
        ),
        ObservationAnswers(
            observation_id="other",
            topic_scores={"chores": 0.9},
            primary_topic="chores",
            behavior_scores={},
            intensity=None,
        ),
    ]
    assert (result.model, result.prompt_version) == ("jev-1.14.0", "conversation-1")
    assert (result.action, result.action_probabilities, result.action_confidence) == (
        "intervene",
        {"intervene": 0.7},
        0.6,
    )


def test_reads_no_action_when_none_was_asked(monkeypatch):
    monkeypatch.setattr(module, "TOPICS", ("chores",))
    row = ObservationInput(
        case_id="case",
        observation_id="other",
        speaker_id="B",
        start_at="1970-01-01T00:00:00Z",
        end_at="1970-01-01T00:00:01Z",
        transcript="Hello",
        signal_level_min=-40,
        signal_level_avg=-30,
        signal_level_max=-20,
    )
    snapshot = DecisionSnapshot(
        case_id="case",
        target_speaker_id="A",
        target_revision=1,
        after_sequence=1,
        through_sequence=2,
        captured_at="1970-01-01T00:01:00Z",
        observations=[row],
        new_observation_ids=["other"],
    )
    questions = {
        "0.topic.chores": Noul(instructions="Topic?"),
        "0.primary": Choice(instructions="Primary?", criteria={"chores": "Chores"}),
    }
    response = SystemOneResponse.model_validate(
        {
            "model": "jev-1.14.0",
            "answers": {
                "0.topic.chores": {"type": "noul", "noul": 0.9},
                "0.primary": {
                    "type": "choice",
                    "choice": "chores",
                    "confidence": 0.8,
                    "probabilities": {"chores": 0.8},
                },
            },
            "usage": {"input_tokens": 100, "output_tokens": 10},
        }
    )

    result = module.read_answers(snapshot=snapshot, questions=questions, response=response)

    assert [row.observation_id for row in result.observations] == ["other"]
    assert (result.action, result.action_probabilities, result.action_confidence) == (
        None,
        {},
        None,
    )
