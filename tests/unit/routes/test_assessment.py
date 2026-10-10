from unittest.mock import Mock

from normative_conformance.routes import assessment


def test_listing_uses_requested_case_and_wraps_records(*, monkeypatch):
    service = Mock(return_value=[])
    monkeypatch.setattr(assessment.assessment, "list_assessment_records", service)
    session = object()
    assert assessment.list_assessments(case_id="requested", session=session).items == []
    service.assert_called_once_with(case_id="requested", session=session)
