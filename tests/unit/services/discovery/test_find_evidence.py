from datetime import UTC
from datetime import datetime
from importlib import import_module
from unittest.mock import Mock

import pytest

from normative_conformance.schemas.assessment import Assessment
from normative_conformance.schemas.assessment import ObservationDecision
from normative_conformance.schemas.decision import PatternEvidence
from normative_conformance.schemas.discovery import DiscoveredModel

module = import_module("normative_conformance.services.discovery.find_evidence")


def _assessment(*, assessment_id, topics):
    return Assessment(
        model="jev-1.14.0",
        prompt_version="conversation-3",
        selection_threshold=0.7,
        observations=[
            ObservationDecision(
                observation_id=str(assessment_id),
                observation_ids=[str(assessment_id)],
                topic_scores={},
                topics=topics,
                primary_topic="unknown",
                behavior_scores={},
                behaviors=[],
                intensity=None,
            )
        ],
        action=None,
        action_probabilities={},
        action_confidence=None,
        assessment_id=assessment_id,
        case_id="case",
        target_speaker_id="speaker-2",
        target_revision=1,
        evaluated_at=datetime(2026, 1, 1, tzinfo=UTC),
        completed_at=datetime(2026, 1, 1, tzinfo=UTC),
        after_sequence=0,
        through_sequence=1,
    )


MODEL = DiscoveredModel(
    normative_model_id=3,
    discovered_at=datetime(2026, 1, 1, tzinfo=UTC),
    topics=["budgeting", "extended_family"],
)


@pytest.mark.parametrize(
    "earlier_topics,expected",
    [
        pytest.param(
            [["extended_family"], ["budgeting"]],
            PatternEvidence(normative_model_id=3, topics=["budgeting", "extended_family"]),
            id="every-required-topic",
        ),
        pytest.param([["extended_family"], ["chores"]], None, id="partial-match"),
    ],
)
def test_evidence_needs_every_required_topic_in_earlier_classifications(
    monkeypatch, earlier_topics, expected
):
    monkeypatch.setattr(module, "newest_model", Mock(return_value=MODEL))
    monkeypatch.setattr(
        module,
        "list_assessment_records",
        Mock(
            return_value=[
                _assessment(assessment_id=index, topics=topics)
                for index, topics in enumerate(earlier_topics, start=1)
            ]
        ),
    )

    assert module.find_evidence(case_id="case", target_revision=1, session=object()) == expected


def test_no_model_gives_no_evidence_without_reading_the_case(monkeypatch):
    monkeypatch.setattr(module, "newest_model", Mock(return_value=None))
    listing = Mock()
    monkeypatch.setattr(module, "list_assessment_records", listing)

    assert module.find_evidence(case_id="case", target_revision=1, session=object()) is None
    listing.assert_not_called()
