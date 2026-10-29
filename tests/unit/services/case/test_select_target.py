from datetime import UTC
from datetime import datetime
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from normative_conformance.errors import StorageUnavailable
from normative_conformance.models.case import ConversationCase
from normative_conformance.models.case import TargetAssignment
from normative_conformance.schemas.case import TargetSelection
from normative_conformance.services.case import records
from normative_conformance.services.case import select_target
from normative_conformance.services.case import target


@pytest.mark.parametrize(
    "existing,labels,input,expected,revision",
    [
        (False, [], {"target_speaker_order": 2}, None, 0),
        (True, ["A", "A"], {"target_speaker_order": 2}, None, 0),
        (True, ["A", "A", "B"], {"target_speaker_order": 2}, "B", 1),
        (True, ["B", "A"], {"target_speaker_id": "B"}, "B", 1),
        (False, [], {"target_speaker_id": "speaker-2"}, "speaker-2", 1),
    ],
)
def test_configures_case_and_commits_selection(
    monkeypatch, existing, labels, input, expected, revision
):
    assignments = []
    cases = []
    session = Mock(spec=Session)
    session.get.return_value = (
        ConversationCase(case_id="case", created_at_us=5) if existing else None
    )
    monkeypatch.setattr(select_target, "speaker_labels", lambda **kwargs: labels)
    session.add.side_effect = lambda row: (
        assignments if isinstance(row, TargetAssignment) else cases
    ).append(row)
    latest = Mock(side_effect=lambda **kwargs: assignments[-1] if assignments else None)
    monkeypatch.setattr(target, "current_assignment", latest)
    monkeypatch.setattr(records, "current_assignment", latest)
    order = []
    session.connection.side_effect = lambda: order.append("lock")
    session.commit.side_effect = lambda: order.append("commit")

    result = select_target.select_target(
        case_id="case",
        selection=TargetSelection(**input),
        session=session,
        now=lambda: datetime(1970, 1, 1, 0, 0, 0, 10, tzinfo=UTC),
    )

    assert result.target_speaker_id == expected
    assert result.target_speaker_order == input.get("target_speaker_order")
    assert result.created_at.microsecond == (5 if existing else 10)
    assert result.target_revision == revision
    assert [row.assigned_at_us for row in assignments] == [10] * revision
    assert [row.case_id for row in cases] == ([] if existing else ["case"])
    assert order == ["lock", "commit"]


def test_selecting_order_replaces_a_label_selection(monkeypatch):
    assignments = [
        TargetAssignment(case_id="case", target_revision=1, assigned_at_us=0, speaker_id="A")
    ]
    session = Mock(spec=Session)
    session.get.return_value = ConversationCase(case_id="case", created_at_us=0)
    monkeypatch.setattr(select_target, "speaker_labels", lambda **kwargs: ["A", "B"])
    session.add.side_effect = assignments.append
    monkeypatch.setattr(target, "current_assignment", lambda **kwargs: assignments[-1])
    monkeypatch.setattr(records, "current_assignment", lambda **kwargs: assignments[-1])

    result = select_target.select_target(
        case_id="case",
        selection=TargetSelection(target_speaker_order=2),
        session=session,
        now=lambda: datetime(1970, 1, 1, tzinfo=UTC),
    )

    assert result.target_speaker_id == "B"
    assert result.target_revision == 2


@pytest.mark.parametrize("stage", ["connection", "add", "commit"])
def test_storage_failure_rolls_back(monkeypatch, stage):
    session = Mock(spec=Session)
    session.get.return_value = ConversationCase(case_id="case", created_at_us=0)
    monkeypatch.setattr(select_target, "speaker_labels", lambda **kwargs: ["A"])
    monkeypatch.setattr(target, "current_assignment", Mock(return_value=None))
    monkeypatch.setattr(records, "current_assignment", Mock(return_value=None))
    error = SQLAlchemyError("database failed")
    getattr(session, stage).side_effect = error
    with pytest.raises(StorageUnavailable) as caught:
        select_target.select_target(
            case_id="case",
            selection=TargetSelection(target_speaker_order=1),
            session=session,
            now=lambda: datetime(1970, 1, 1, tzinfo=UTC),
        )
    assert caught.value.__cause__ is error
    session.rollback.assert_called_once()
