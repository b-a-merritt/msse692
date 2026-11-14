from unittest.mock import Mock

import pytest
from sqlmodel import Session

from conversation_monitor.errors import NotFound
from conversation_monitor.models.case import ConversationCase
from conversation_monitor.models.case import TargetAssignment
from conversation_monitor.services.case import get_case
from conversation_monitor.services.case import records


def test_get_case_returns_stored_selection(monkeypatch):
    session = Mock(spec=Session)
    session.get.return_value = ConversationCase(
        case_id="case", created_at_us=4, target_speaker_order=2
    )
    monkeypatch.setattr(
        records,
        "current_assignment",
        Mock(
            return_value=TargetAssignment(
                case_id="case", target_revision=1, assigned_at_us=0, speaker_id="B"
            )
        ),
    )
    result = get_case.get_case(case_id="case", session=session)
    assert result.case_id == "case"
    assert result.created_at.microsecond == 4
    assert result.target_speaker_order == 2
    assert result.target_speaker_id == "B"
    assert result.target_revision == 1
    session.get.assert_called_once_with(ConversationCase, "case")


def test_missing_case_is_not_found():
    session = Mock(spec=Session)
    session.get.return_value = None
    with pytest.raises(NotFound):
        get_case.get_case(case_id="missing", session=session)
