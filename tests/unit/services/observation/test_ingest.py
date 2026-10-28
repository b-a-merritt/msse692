from datetime import UTC
from datetime import datetime
from importlib import import_module
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from normative_conformance.errors import ObservationExists
from normative_conformance.errors import StorageUnavailable
from normative_conformance.models.case import ConversationCase
from normative_conformance.models.case import TargetAssignment
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.services.case import target

module = import_module("normative_conformance.services.observation.ingest")


@pytest.mark.parametrize(
    "existing_case,last_sequence,new_cases,sequence,assignments",
    [
        pytest.param(None, None, [("case", 1_000_000)], 1, [], id="new-case"),
        pytest.param(
            ConversationCase(case_id="case", created_at_us=0), 7, [], 8, [], id="existing-case"
        ),
        pytest.param(
            ConversationCase(case_id="case", created_at_us=0, target_speaker_order=2),
            2,
            [],
            3,
            [(1, 1_000_000, "B")],
            id="speaking-order-resolves",
        ),
    ],
)
def test_assigns_receipt_sequence_and_commits(
    *, monkeypatch, existing_case, last_sequence, new_cases, sequence, assignments
):
    monkeypatch.setattr(target, "current_assignment", Mock(return_value=None))
    input = ObservationInput(
        case_id="case",
        observation_id="chunk",
        speaker_id="subject",
        start_at="1970-01-01T00:00:00.000001Z",
        end_at="1970-01-01T00:00:00.000009Z",
        transcript=" Hello ",
        signal_level_min=-50,
        signal_level_avg=-30,
        signal_level_max=-10,
    )
    session = Mock(spec=Session)
    session.get.return_value = existing_case
    session.exec.return_value.first.return_value = None
    session.exec.return_value.one.return_value = last_sequence
    session.exec.return_value.all.return_value = ["A", "A", "B"]
    order = []
    session.connection.side_effect = lambda: order.append("lock")
    session.commit.side_effect = lambda: order.append("commit")

    def clock():
        order.append("clock")
        return datetime(1970, 1, 1, 0, 0, 1, tzinfo=UTC)

    result = module.ingest(input=input, session=session, now=clock)

    assert order == ["lock", "clock", "commit"]
    assert result.sequence == sequence
    assert result.received_at == datetime(1970, 1, 1, 0, 0, 1, tzinfo=UTC)
    rows = [call.args[0] for call in session.add.call_args_list]
    assert [
        (row.case_id, row.created_at_us) for row in rows if isinstance(row, ConversationCase)
    ] == new_cases
    assert [row.model_dump() for row in rows if isinstance(row, Observation)] == [
        {
            "observation_key": None,
            "case_id": "case",
            "observation_id": "chunk",
            "speaker_revision_id": None,
            "sequence": sequence,
            "received_at_us": 1_000_000,
            "speaker_id": "subject",
            "start_at_us": 1,
            "end_at_us": 9,
            "transcript": " Hello ",
            "signal_level_min": -50,
            "signal_level_avg": -30,
            "signal_level_max": -10,
        }
    ]
    assert [
        (row.target_revision, row.assigned_at_us, row.speaker_id)
        for row in rows
        if isinstance(row, TargetAssignment)
    ] == assignments
    session.rollback.assert_not_called()


def test_duplicate_is_rejected_without_storing_anything():
    session = Mock(spec=Session)
    session.get.return_value = ConversationCase(case_id="case", created_at_us=0)
    session.exec.return_value.first.return_value = object()
    with pytest.raises(ObservationExists, match="An observation with this identity already exists"):
        module.ingest(
            input=ObservationInput(
                case_id="case",
                observation_id="chunk",
                speaker_id="subject",
                start_at="1970-01-01T00:00:00Z",
                end_at="1970-01-01T00:00:01Z",
                transcript="hello",
                signal_level_min=-50,
                signal_level_avg=-30,
                signal_level_max=-10,
            ),
            session=session,
            now=lambda: datetime(1970, 1, 1, tzinfo=UTC),
        )
    session.rollback.assert_called_once()
    session.add.assert_not_called()


@pytest.mark.parametrize("stage", ["connection", "commit"])
def test_storage_failures_roll_back_with_a_safe_message(*, monkeypatch, stage):
    monkeypatch.setattr(target, "current_assignment", Mock(return_value=None))
    session = Mock(spec=Session)
    session.get.return_value = ConversationCase(case_id="case", created_at_us=0)
    session.exec.return_value.first.return_value = None
    session.exec.return_value.one.return_value = 0
    error = SQLAlchemyError("Private driver details")
    getattr(session, stage).side_effect = error
    with pytest.raises(
        StorageUnavailable, match=r"^The observation could not be stored$"
    ) as caught:
        module.ingest(
            input=ObservationInput(
                case_id="case",
                observation_id="chunk",
                speaker_id="subject",
                start_at="1970-01-01T00:00:00Z",
                end_at="1970-01-01T00:00:01Z",
                transcript="hello",
                signal_level_min=-50,
                signal_level_avg=-30,
                signal_level_max=-10,
            ),
            session=session,
            now=lambda: datetime(1970, 1, 1, tzinfo=UTC),
        )
    assert caught.value.__cause__ is error
    session.rollback.assert_called_once()
