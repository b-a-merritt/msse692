from datetime import datetime
from datetime import timezone
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from normative_conformance.errors import NotFound
from normative_conformance.errors import StorageUnavailable
from normative_conformance.models.case import CaseLog
from normative_conformance.schemas.case import TargetSelection
from normative_conformance.services.case import selection


@pytest.mark.parametrize(
    "existing,labels,input,expected,manual",
    [
        (False, [], {"target_speaker_order": 2}, None, False),
        (True, ["A", "A"], {"target_speaker_order": 2}, None, False),
        (True, ["A", "A", "B"], {"target_speaker_order": 2}, "B", False),
        (True, ["B", "A"], {"target_speaker_id": "B"}, "B", True),
        (False, [], {"target_speaker_id": "speaker-2"}, "speaker-2", True),
    ],
)
def test_configures_case_and_commits_selection(
    monkeypatch, existing, labels, input, expected, manual
):
    case = CaseLog(case_id="case", created_at_us=5)
    session = Mock(spec=Session)
    session.get.return_value = case if existing else None
    session.exec.return_value.all.return_value = labels
    clock = Mock(return_value=datetime(1970, 1, 1, 0, 0, 0, 10, tzinfo=timezone.utc))
    order = []
    session.connection.side_effect = lambda: order.append("lock")
    session.commit.side_effect = lambda: order.append("commit")
    result = selection.select_target(
        case_id="case",
        selection=TargetSelection(**input),
        session=session,
        now=clock,
    )
    assert result.target_speaker_id == expected
    assert result.target_speaker_manual is manual
    assert result.target_speaker_order == input.get("target_speaker_order")
    assert result.created_at.microsecond == (5 if existing else 10)
    assert result.target_revision == (0 if expected is None else 1)
    assert order.index("lock") < order.index("commit")
    if existing:
        clock.assert_not_called()
    else:
        assert session.add.call_args.args[0].case_id == "case"


def test_selecting_order_explicitly_releases_manual_override(monkeypatch):
    case = CaseLog(
        case_id="case",
        created_at_us=0,
        target_speaker_id="A",
        target_speaker_order=2,
        target_speaker_manual=True,
        target_revision=1,
    )
    session = Mock(spec=Session)
    session.get.return_value = case
    session.exec.return_value.all.return_value = ["A", "B"]
    result = selection.select_target(
        case_id="case",
        selection=TargetSelection(target_speaker_order=2),
        session=session,
        now=lambda: datetime(1970, 1, 1, tzinfo=timezone.utc),
    )
    assert result.target_speaker_id == "B"
    assert not result.target_speaker_manual
    assert result.target_revision == 2


@pytest.mark.parametrize("stage", ["connection", "exec", "commit"])
def test_storage_failure_rolls_back(monkeypatch, stage):
    session = Mock(spec=Session)
    session.get.return_value = CaseLog(case_id="case", created_at_us=0)
    session.exec.return_value.all.return_value = ["A"]
    error = SQLAlchemyError("database failed")
    getattr(session, stage).side_effect = error
    with pytest.raises(StorageUnavailable) as caught:
        selection.select_target(
            case_id="case",
            selection=TargetSelection(target_speaker_id="A"),
            session=session,
            now=lambda: datetime(1970, 1, 1, tzinfo=timezone.utc),
        )
    assert caught.value.__cause__ is error
    session.rollback.assert_called_once()


def test_get_case_returns_stored_selection():
    session = Mock(spec=Session)
    session.get.return_value = CaseLog(
        case_id="case",
        created_at_us=4,
        target_speaker_order=2,
        target_speaker_id="B",
        target_revision=1,
    )
    result = selection.get_case(case_id="case", session=session)
    assert result.case_id == "case"
    assert result.created_at.microsecond == 4
    assert result.target_speaker_order == 2
    assert result.target_speaker_id == "B"
    assert result.target_revision == 1
    assert not result.target_speaker_manual
    session.get.assert_called_once_with(CaseLog, "case")


def test_missing_case_is_not_found():
    session = Mock(spec=Session)
    session.get.return_value = None
    with pytest.raises(NotFound):
        selection.get_case(case_id="missing", session=session)
