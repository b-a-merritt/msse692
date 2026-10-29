from datetime import UTC
from datetime import datetime
from importlib import import_module
from unittest.mock import Mock

from sqlmodel import Session

from normative_conformance.schemas.assessment import Assessment
from normative_conformance.schemas.assessment import ObservationDecision
from normative_conformance.schemas.case import CaseRecord
from normative_conformance.schemas.discovery import CaseTrace

module = import_module("normative_conformance.services.discovery.load_traces")


def _assessment(*, assessment_id, target_revision, topics):
    return Assessment(
        model="jev-1.14.0",
        prompt_version="conversation-2",
        selection_threshold=0.7,
        observations=[
            ObservationDecision(
                observation_id="one",
                observation_ids=["one"],
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
        target_revision=target_revision,
        evaluated_at=datetime(2026, 1, 1, tzinfo=UTC),
        completed_at=datetime(2026, 1, 1, tzinfo=UTC),
        after_sequence=0,
        through_sequence=1,
    )


def test_traces_each_case_for_its_current_target(*, monkeypatch):
    session = Mock(spec=Session)
    monkeypatch.setattr(
        module,
        "list_cases",
        lambda *, session: [
            CaseRecord(
                case_id="case",
                created_at="1970-01-01T00:00:00Z",
                target_speaker_order=None,
                target_speaker_id="speaker-2",
                target_revision=2,
            )
        ],
    )
    records = [
        _assessment(assessment_id=1, target_revision=1, topics=["budgeting"]),
        _assessment(assessment_id=2, target_revision=2, topics=["chores"]),
    ]
    listing = Mock(return_value=records)
    monkeypatch.setattr(module, "list_assessment_records", listing)

    assert module.load_traces(session=session) == [CaseTrace(events=["chores"], assessment_ids=[2])]
    listing.assert_called_once_with(case_id="case", session=session)
