from typesafe_sdk import Choice
from typesafe_sdk import Noul
from typesafe_sdk import Score

from normative_conformance.schemas.decision import DecisionSnapshot
from normative_conformance.services.decision.topics import TOPICS
from normative_conformance.services.decision.wording import ACTION_QUESTION
from normative_conformance.services.decision.wording import ACTIONS
from normative_conformance.services.decision.wording import BEHAVIOR_QUESTIONS
from normative_conformance.services.decision.wording import HOSTILITY_LEVELS
from normative_conformance.services.decision.wording import HOSTILITY_QUESTION
from normative_conformance.services.decision.wording import OBSERVATION_REFERENCE
from normative_conformance.services.decision.wording import PREAMBLE
from normative_conformance.services.decision.wording import PRIMARY_TOPIC_QUESTION
from normative_conformance.services.decision.wording import TOPIC_QUESTION
from normative_conformance.services.decision.wording import UNKNOWN_TOPIC

ACTION_KEY = "action"
Question = Noul | Choice | Score


def question_key(index: int, *names: str) -> str:
    return ".".join((str(index), *names))


def build_questions(*, snapshot: DecisionSnapshot) -> dict[str, Question]:
    questions: dict[str, Question] = {}
    for index, row in enumerate(snapshot.observations):
        if row.observation_id in snapshot.new_observation_ids:
            questions |= _topic_questions(index=index)
            if row.speaker_id == snapshot.target_speaker_id:
                questions |= _behavior_questions(index=index)
    questions[ACTION_KEY] = Choice(instructions=PREAMBLE + ACTION_QUESTION, criteria=ACTIONS)
    return questions


def _topic_questions(*, index: int) -> dict[str, Question]:
    questions: dict[str, Question] = {
        question_key(index, "topic", topic): Noul(
            instructions=_instructions(
                index=index, question=TOPIC_QUESTION.format(topic=_label(topic))
            )
        )
        for topic in TOPICS
    }
    questions[question_key(index, "primary")] = Choice(
        instructions=_instructions(index=index, question=PRIMARY_TOPIC_QUESTION),
        criteria={**{topic: _label(topic) for topic in TOPICS}, "unknown": UNKNOWN_TOPIC},
    )
    return questions


def _behavior_questions(*, index: int) -> dict[str, Question]:
    questions: dict[str, Question] = {
        question_key(index, "behavior", behavior): Noul(
            instructions=_instructions(index=index, question=question)
        )
        for behavior, question in BEHAVIOR_QUESTIONS.items()
    }
    questions[question_key(index, "intensity")] = Score(
        instructions=_instructions(index=index, question=HOSTILITY_QUESTION),
        criteria=HOSTILITY_LEVELS,
    )
    return questions


def _instructions(*, index: int, question: str) -> str:
    return PREAMBLE + OBSERVATION_REFERENCE.format(index=index) + question


def _label(topic: str) -> str:
    return topic.replace("_", " ")
