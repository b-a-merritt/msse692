from unittest.mock import Mock

from sqlmodel import Session

from conversation_monitor.models.case import ConversationCase
from conversation_monitor.models.case import TargetAssignment
from conversation_monitor.services.case import records
from conversation_monitor.services.case.list_cases import list_cases


def test_reports_each_case_with_its_current_target(monkeypatch):
    session = Mock(spec=Session)
    session.exec.return_value = [
        ConversationCase(case_id="a", created_at_us=1),
        ConversationCase(case_id="b", created_at_us=2),
    ]
    assignments = {
        "a": TargetAssignment(case_id="a", target_revision=3, assigned_at_us=0, speaker_id="B"),
        "b": None,
    }
    monkeypatch.setattr(
        records, "current_assignment", lambda *, case_id, session: assignments[case_id]
    )

    assert [
        (case.case_id, case.target_speaker_id, case.target_revision)
        for case in list_cases(session=session)
    ] == [("a", "B", 3), ("b", None, 0)]
