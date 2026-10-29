from typesafe_sdk import Choice
from typesafe_sdk import Noul
from typesafe_sdk import Score

from normative_conformance.schemas.decision import DecisionSnapshot
from normative_conformance.services.decision.topics import TOPICS
from normative_conformance.services.decision.turns import turns
from normative_conformance.services.decision.wording import ACTION_QUESTION
from normative_conformance.services.decision.wording import ACTIONS
from normative_conformance.services.decision.wording import BEHAVIOR_QUESTIONS
from normative_conformance.services.decision.wording import HOSTILITY_LEVELS
from normative_conformance.services.decision.wording import HOSTILITY_QUESTION
from normative_conformance.services.decision.wording import PREAMBLE
from normative_conformance.services.decision.wording import PRIMARY_TOPIC_QUESTION
from normative_conformance.services.decision.wording import ROW_REFERENCE
from normative_conformance.services.decision.wording import TOPIC_QUESTION
from normative_conformance.services.decision.wording import TURN_REFERENCE
from normative_conformance.services.decision.wording import UNKNOWN_TOPIC

ACTION_KEY = "action"
Question = Noul | Choice | Score


def question_key(index: int, *names: str) -> str:
    return ".".join((str(index), *names))


def build_questions(*, snapshot: DecisionSnapshot) -> dict[str, Question]:
    """Ask about each turn of new speech, keyed by the row index of its first observation."""
    indexes = {row.observation_id: index for index, row in enumerate(snapshot.observations)}
    new = [
        row for row in snapshot.observations if row.observation_id in snapshot.new_observation_ids
    ]
    questions: dict[str, Question] = {}
    for turn in turns(observations=new):
        rows = [indexes[row.observation_id] for row in turn]
        questions |= _topic_questions(rows=rows)
        if turn[0].speaker_id == snapshot.target_speaker_id:
            questions |= _behavior_questions(rows=rows)

    # Only new target speech can change what the target should be prompted about.
    if any(row.speaker_id == snapshot.target_speaker_id for row in new):
        questions[ACTION_KEY] = Choice(instructions=PREAMBLE + ACTION_QUESTION, criteria=ACTIONS)

    return questions


def _topic_questions(*, rows: list[int]) -> dict[str, Question]:
    questions: dict[str, Question] = {
        question_key(rows[0], "topic", topic): Noul(
            instructions=_instructions(
                rows=rows, question=TOPIC_QUESTION.format(topic=_label(topic))
            )
        )
        for topic in TOPICS
    }
    questions[question_key(rows[0], "primary")] = Choice(
        instructions=_instructions(rows=rows, question=PRIMARY_TOPIC_QUESTION),
        criteria={**{topic: _label(topic) for topic in TOPICS}, "unknown": UNKNOWN_TOPIC},
    )
    return questions


def _behavior_questions(*, rows: list[int]) -> dict[str, Question]:
    questions: dict[str, Question] = {
        question_key(rows[0], "behavior", behavior): Noul(
            instructions=_instructions(rows=rows, question=question)
        )
        for behavior, question in BEHAVIOR_QUESTIONS.items()
    }
    questions[question_key(rows[0], "intensity")] = Score(
        instructions=_instructions(rows=rows, question=HOSTILITY_QUESTION),
        criteria=HOSTILITY_LEVELS,
    )
    return questions


def _instructions(*, rows: list[int], question: str) -> str:
    reference = ", ".join(ROW_REFERENCE.format(index=index) for index in rows)
    return PREAMBLE + TURN_REFERENCE.format(rows=reference) + question


def _label(topic: str) -> str:
    return topic.replace("_", " ")
