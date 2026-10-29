from datetime import UTC
from datetime import datetime

import pytest

from normative_conformance.schemas.assessment import Assessment
from normative_conformance.schemas.assessment import ObservationDecision
from normative_conformance.schemas.discovery import CaseTrace
from normative_conformance.services.discovery.trace import trace


def _assessment(*, assessment_id, target_revision, turns):
    """Build an assessment whose turns are (topics, behaviors) at the threshold."""
    return Assessment(
        model="jev-1.14.0",
        prompt_version="conversation-2",
        selection_threshold=0.7,
        observations=[
            ObservationDecision(
                observation_id=f"{assessment_id}-{index}",
                observation_ids=[f"{assessment_id}-{index}"],
                topic_scores={},
                topics=topics,
                primary_topic="unknown",
                behavior_scores={},
                behaviors=behaviors,
                intensity=None,
            )
            for index, (topics, behaviors) in enumerate(turns)
        ],
        action=None,
        action_probabilities={},
        action_confidence=None,
        assessment_id=assessment_id,
        case_id="case",
        target_speaker_id="speaker-2",
        target_revision=target_revision,
        evaluated_at=datetime(2026, 1, 1, tzinfo=UTC),
        completed_at=datetime(2026, 1, 1, tzinfo=UTC),
        after_sequence=0,
        through_sequence=1,
    )


def test_lists_each_topic_once_in_assessment_and_turn_order():
    first = _assessment(
        assessment_id=1,
        target_revision=1,
        turns=[(["chores", "planning"], []), (["planning"], [])],
    )
    second = _assessment(
        assessment_id=2,
        target_revision=1,
        turns=[(["budgeting", "chores"], [])],
    )
    assert trace(assessments=[second, first], target_revision=1) == CaseTrace(
        events=["chores", "planning", "budgeting"], assessment_ids=[1, 2]
    )


@pytest.mark.parametrize(
    "behavior",
    ["criticism", "contempt", "cruelty", "defensiveness", "stonewalling", "interruption"],
)
def test_first_undesired_behavior_ends_the_trace_with_its_assessment(behavior):
    before = _assessment(assessment_id=1, target_revision=1, turns=[(["extended_family"], [])])
    # The other speaker's turn in the same batch was not known before the request either.
    attack = _assessment(
        assessment_id=2,
        target_revision=1,
        turns=[(["budgeting"], []), (["interpersonal_conflict"], [behavior])],
    )
    after = _assessment(assessment_id=3, target_revision=1, turns=[(["chores"], [])])
    # The ending assessment is a source; later ones contributed nothing.
    assert trace(assessments=[before, attack, after], target_revision=1) == CaseTrace(
        events=["extended_family", "undesired_behavior"], assessment_ids=[1, 2]
    )


def test_swearing_alone_does_not_end_the_trace():
    swearing = _assessment(assessment_id=1, target_revision=1, turns=[(["work"], ["swearing"])])
    assert trace(assessments=[swearing], target_revision=1).events == ["work"]


def test_only_the_given_target_revision_counts():
    earlier_target = _assessment(
        assessment_id=1, target_revision=1, turns=[(["budgeting"], ["contempt"])]
    )
    current_target = _assessment(assessment_id=2, target_revision=2, turns=[(["chores"], [])])
    assert trace(assessments=[earlier_target, current_target], target_revision=2) == CaseTrace(
        events=["chores"], assessment_ids=[2]
    )


def test_no_assessments_have_no_topics():
    assert trace(assessments=[], target_revision=1) == CaseTrace(events=[], assessment_ids=[])
