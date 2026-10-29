from unittest.mock import Mock

import pytest
from sqlmodel import Session

from normative_conformance.schemas.decision import DecisionAnswers
from normative_conformance.schemas.decision import ObservationAnswers
from normative_conformance.services.intervention import create_intervention as module


def _answers(*, action, behavior_scores):
    return DecisionAnswers(
        model="jev-1.14.0",
        prompt_version="conversation-1",
        observations=[
            ObservationAnswers(
                observation_id=str(index),
                topic_scores={},
                primary_topic="unknown",
                behavior_scores=scores,
                intensity=None,
            )
            for index, scores in enumerate(behavior_scores)
        ],
        action=action,
        action_probabilities={},
        action_confidence=None if action is None else 0.9,
    )


@pytest.mark.parametrize("action", ["remain_silent", "await_context", "reflect_later", None])
def test_other_actions_create_nothing(action):
    session = Mock(spec=Session)
    answers = _answers(action=action, behavior_scores=[{"criticism": 0.9}])

    assert (
        module.create_intervention(
            assessment_id=7,
            created_at_us=100,
            answers=answers,
            session=session,
        )
        is None
    )
    session.add.assert_not_called()


@pytest.mark.parametrize(
    "behavior_scores,expected",
    [
        pytest.param(
            [{"criticism": 0.8, "swearing": 0.2}, {"contempt": 0.95}],
            module.MESSAGES["contempt"],
            id="strongest-behavior-across-observations",
        ),
        pytest.param(
            [{"criticism": 0.7}],
            module.MESSAGES["criticism"],
            id="behavior-at-the-threshold",
        ),
        pytest.param(
            [{"criticism": 0.69}], module.GENERAL_MESSAGE, id="no-behavior-meets-the-threshold"
        ),
        pytest.param([{}], module.GENERAL_MESSAGE, id="no-behavior-scores"),
    ],
)
def test_intervene_adds_a_prompt_for_the_strongest_behavior(behavior_scores, expected):
    session = Mock(spec=Session)
    answers = _answers(action="intervene", behavior_scores=behavior_scores)

    intervention = module.create_intervention(
        assessment_id=7,
        created_at_us=100,
        answers=answers,
        session=session,
    )

    session.add.assert_called_once_with(intervention)
    assert (intervention.assessment_id, intervention.created_at_us) == (7, 100)
    assert intervention.message == expected
    assert intervention.sent_at_us is None
