from datetime import datetime
from datetime import timezone
from importlib import import_module
from unittest.mock import Mock

from sqlmodel import Session

from normative_conformance.models.intervention import Intervention
from normative_conformance.models.intervention import InterventionSource

module = import_module("normative_conformance.services.intervention.list_intervention_records")


def test_converts_delivery_status_and_groups_sorted_sources(*, monkeypatch):
    session = Mock(spec=Session)
    rows = [
        Intervention(
            intervention_id=2, case_id="case", message="First", created_at_us=100, sent_at_us=None
        ),
        Intervention(
            intervention_id=3, case_id="case", message="Second", created_at_us=101, sent_at_us=110
        ),
    ]
    listing = Mock(return_value=rows)
    subject = Mock(return_value="subject")
    monkeypatch.setattr(module, "list_interventions", listing)
    monkeypatch.setattr(module, "get_subject_speaker_id", subject)
    session.exec.return_value = [
        InterventionSource(intervention_id=2, assessment_id=4),
        InterventionSource(intervention_id=3, assessment_id=5),
        InterventionSource(intervention_id=2, assessment_id=6),
    ]
    results = module.list_intervention_records(
        session=session, case_id="case", status=None, intervention_ids=[2, 3]
    )
    listing.assert_called_once_with(
        session=session, case_id="case", status=None, intervention_ids=[2, 3]
    )
    assert [row.assessment_ids for row in results] == [[4, 6], [5]]
    assert [row.status for row in results] == ["pending", "sent"]
    assert results[0].sent_at is None
    assert results[1].sent_at == datetime(1970, 1, 1, 0, 0, 0, 110, tzinfo=timezone.utc)
    assert [row.message for row in results] == ["First", "Second"]
    assert all(row.subject_speaker_id == "subject" for row in results)
    subject.assert_called_once_with(session=session)


def test_empty_result_needs_no_subject_or_source_lookup(*, monkeypatch):
    session = Mock(spec=Session)
    monkeypatch.setattr(module, "list_interventions", Mock(return_value=[]))
    subject = Mock()
    monkeypatch.setattr(module, "get_subject_speaker_id", subject)
    assert module.list_intervention_records(session=session) == []
    subject.assert_not_called()
    session.exec.assert_not_called()
