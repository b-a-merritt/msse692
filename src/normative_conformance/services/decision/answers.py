"""Read the decision model's answers for the questions that were asked."""

from typing import cast

from typesafe_sdk import SystemOneResponse

from normative_conformance.schemas.decision import Action
from normative_conformance.schemas.decision import DecisionAnswers
from normative_conformance.schemas.decision import DecisionSnapshot
from normative_conformance.schemas.decision import ObservationAnswers
from normative_conformance.services.decision.questions import ACTION_KEY
from normative_conformance.services.decision.questions import Question
from normative_conformance.services.decision.questions import question_key
from normative_conformance.services.decision.topics import TOPICS
from normative_conformance.services.decision.wording import BEHAVIOR_QUESTIONS
from normative_conformance.services.decision.wording import PROMPT_VERSION


def read_answers(
    *,
    snapshot: DecisionSnapshot,
    questions: dict[str, Question],
    response: SystemOneResponse,
) -> DecisionAnswers:
    """Read answers about each observation that was asked about, then the action."""
    action = response.choices[ACTION_KEY]
    return DecisionAnswers(
        model=response.model,
        prompt_version=PROMPT_VERSION,
        observations=[
            _observation_answers(
                index=index,
                observation_id=row.observation_id,
                questions=questions,
                response=response,
            )
            for index, row in enumerate(snapshot.observations)
            if question_key(index, "primary") in questions
        ],
        action=cast(Action, action.choice),
        action_probabilities=action.probabilities,
        action_confidence=action.confidence,
    )


def _observation_answers(
    *,
    index: int,
    observation_id: str,
    questions: dict[str, Question],
    response: SystemOneResponse,
) -> ObservationAnswers:
    topic_scores, primary_topic = _topic_answers(index=index, response=response)
    behavior_scores: dict[str, float] = {}
    intensity = None
    if question_key(index, "intensity") in questions:
        behavior_scores, intensity = _behavior_answers(index=index, response=response)
    return ObservationAnswers(
        observation_id=observation_id,
        topic_scores=topic_scores,
        primary_topic=primary_topic,
        behavior_scores=behavior_scores,
        intensity=intensity,
    )


def _topic_answers(*, index: int, response: SystemOneResponse) -> tuple[dict[str, float], str]:
    """Read whether the speech is about each topic, then which topic is primary."""
    scores = {topic: response.nouls[question_key(index, "topic", topic)].noul for topic in TOPICS}
    return scores, response.choices[question_key(index, "primary")].choice


def _behavior_answers(*, index: int, response: SystemOneResponse) -> tuple[dict[str, float], float]:
    """Read whether the speech shows each behavior, then how hostile it is."""
    scores = {
        behavior: response.nouls[question_key(index, "behavior", behavior)].noul
        for behavior in BEHAVIOR_QUESTIONS
    }
    return scores, response.scores[question_key(index, "intensity")].score
