from unittest.mock import Mock

from sqlmodel import Session

from normative_conformance.models.case import ConversationCase
from normative_conformance.services.case import records
from normative_conformance.services.case.ensure_case import ensure_case


def test_existing_case_is_returned_unchanged(monkeypatch):
    session = Mock(spec=Session)
    session.get.return_value = ConversationCase(
        case_id="case", created_at_us=4, target_speaker_order=2
    )
    monkeypatch.setattr(records, "current_assignment", Mock(return_value=None))

    result = ensure_case(case_id="case", created_at_us=9, session=session)

    assert (result.created_at.microsecond, result.target_speaker_order) == (4, 2)
    session.add.assert_not_called()


def test_missing_case_is_created_without_committing(monkeypatch):
    session = Mock(spec=Session)
    session.get.return_value = None
    monkeypatch.setattr(records, "current_assignment", Mock(return_value=None))

    result = ensure_case(case_id="case", created_at_us=9, session=session)

    [created] = [call.args[0] for call in session.add.call_args_list]
    assert (created.case_id, created.created_at_us) == ("case", 9)
    assert (result.case_id, result.created_at.microsecond, result.target_revision) == ("case", 9, 0)
    session.flush.assert_called_once()
    session.commit.assert_not_called()
