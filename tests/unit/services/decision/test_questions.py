from datetime import UTC
from datetime import datetime

from typesafe_sdk import Choice
from typesafe_sdk import Noul
from typesafe_sdk import Score

from normative_conformance.schemas.decision import DecisionSnapshot
from normative_conformance.schemas.decision import PatternEvidence
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.services.decision.questions import build_questions
from normative_conformance.services.decision.wording import ACTIONS
from normative_conformance.services.decision.wording import INTERVENE_WITH_EVIDENCE


def test_questions_reference_explicit_rows_and_classify_only_new_turns():
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
    target = context.model_copy(
        update={
            "observation_id": "target",
            "start_at": datetime(1970, 1, 1, second=1, tzinfo=UTC),
            "end_at": datetime(1970, 1, 1, second=2, tzinfo=UTC),
        }
    )
    continued = context.model_copy(
        update={
            "observation_id": "continued",
            "start_at": datetime(1970, 1, 1, second=2, tzinfo=UTC),
            "end_at": datetime(1970, 1, 1, second=3, tzinfo=UTC),
        }
    )
    other = context.model_copy(
        update={
            "observation_id": "other",
            "speaker_id": "B",
            "start_at": datetime(1970, 1, 1, second=3, tzinfo=UTC),
            "end_at": datetime(1970, 1, 1, second=4, tzinfo=UTC),
        }
    )
    snapshot = DecisionSnapshot(
        case_id="case",
        target_speaker_id="A",
        target_revision=1,
        after_sequence=1,
        through_sequence=4,
        captured_at="1970-01-01T00:01:00Z",
        observations=[context, target, continued, other],
        new_observation_ids=["target", "continued", "other"],
    )
    questions = build_questions(snapshot=snapshot, evidence=None)
    # Context (0) is not asked about, and the target's turn (1-2) is asked about once.
    assert {key.split(".")[0] for key in questions} == {"1", "3", "action"}
    assert isinstance(questions["1.topic.chores"], Noul)
    assert (
        "For the turn spoken in `observations[1]`, `observations[2]`: Is this turn about chores?"
        in questions["1.topic.chores"].instructions
    )
    assert "`observations[3]`: " in questions["3.primary"].instructions
    assert isinstance(questions["3.primary"], Choice)
    assert "unknown" in questions["3.primary"].criteria
    assert isinstance(questions["1.intensity"], Score)
    assert "3.intensity" not in questions
    assert not any(key.startswith("3.behavior.") for key in questions)
    assert set(questions["action"].criteria) == {
        "remain_silent",
        "await_context",
        "reflect_later",
        "intervene",
    }
    assert "apologies" in questions["action"].instructions
    assert questions["action"].criteria == ACTIONS


def test_batches_without_new_target_speech_are_not_asked_for_an_action():
    target = ObservationInput(
        case_id="case",
        observation_id="target",
        speaker_id="A",
        start_at="1970-01-01T00:00:00Z",
        end_at="1970-01-01T00:00:01Z",
        transcript="Hello",
        signal_level_min=-40,
        signal_level_avg=-30,
        signal_level_max=-20,
    )
    other = target.model_copy(update={"observation_id": "other", "speaker_id": "B"})
    snapshot = DecisionSnapshot(
        case_id="case",
        target_speaker_id="A",
        target_revision=1,
        after_sequence=1,
        through_sequence=2,
        captured_at="1970-01-01T00:01:00Z",
        # Earlier target speech is context only, so it does not call for an action.
        observations=[target, other],
        new_observation_ids=["other"],
    )
    questions = build_questions(snapshot=snapshot, evidence=None)
    assert isinstance(questions["1.primary"], Choice)
    assert "action" not in questions


def test_evidence_reaches_only_the_action_question_and_widens_intervene():
    target = ObservationInput(
        case_id="case",
        observation_id="target",
        speaker_id="A",
        start_at="1970-01-01T00:00:00Z",
        end_at="1970-01-01T00:00:01Z",
        transcript="Your mother again?",
        signal_level_min=-40,
        signal_level_avg=-30,
        signal_level_max=-20,
    )
    snapshot = DecisionSnapshot(
        case_id="case",
        target_speaker_id="A",
        target_revision=1,
        after_sequence=0,
        through_sequence=1,
        captured_at="1970-01-01T00:01:00Z",
        observations=[target],
        new_observation_ids=["target"],
    )
    evidence = PatternEvidence(normative_model_id=3, topics=["budgeting", "extended_family"])

    questions = build_questions(snapshot=snapshot, evidence=evidence)

    action = questions["action"]
    assert "come up in this conversation: budgeting, extended family." in action.instructions
    assert "never justifies intervention by itself" in action.instructions
    assert action.criteria == {**ACTIONS, "intervene": INTERVENE_WITH_EVIDENCE}
    assert not any(
        "used to discover this pattern" in question.instructions
        for key, question in questions.items()
        if key != "action"
    )
