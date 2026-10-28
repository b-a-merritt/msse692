from datetime import UTC
from datetime import datetime
from importlib import import_module
from unittest.mock import Mock

from sqlmodel import Session

from normative_conformance.models.intervention import Intervention

module = import_module("normative_conformance.services.intervention.list_intervention_records")


def test_converts_delivery_status_and_source_assessment(*, monkeypatch):
    session = Mock(spec=Session)
    rows = [
        (
            Intervention(
                intervention_id=2,
                assessment_id=4,
                message="First",
                created_at_us=100,
                sent_at_us=None,
            ),
            "case",
            "subject",
        ),
        (
            Intervention(
                intervention_id=3,
                assessment_id=5,
                message="Second",
                created_at_us=101,
                sent_at_us=110,
            ),
            "case",
            "subject",
        ),
    ]
    listing = Mock(return_value=rows)
    monkeypatch.setattr(module, "list_interventions", listing)
    results = module.list_intervention_records(
        session=session, case_id="case", status=None, intervention_ids=[2, 3]
    )
    listing.assert_called_once_with(
        session=session, case_id="case", status=None, intervention_ids=[2, 3]
    )
    assert [row.assessment_id for row in results] == [4, 5]
    assert [row.status for row in results] == ["pending", "sent"]
    assert results[0].sent_at is None
    assert results[1].sent_at == datetime(1970, 1, 1, 0, 0, 0, 110, tzinfo=UTC)
    assert [row.message for row in results] == ["First", "Second"]
    assert all(row.case_id == "case" for row in results)
    assert all(row.target_speaker_id == "subject" for row in results)
