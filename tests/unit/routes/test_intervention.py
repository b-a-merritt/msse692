from unittest.mock import Mock

from normative_conformance.routes import intervention


def test_listing_forwards_case_and_delivery_status_filters(*, monkeypatch):
    service = Mock(return_value=[])
    monkeypatch.setattr(intervention.intervention, "list_intervention_records", service)
    session = object()
    assert (
        intervention.list_interventions(
            case_id="requested", status="pending", session=session
        ).items
        == []
    )
    service.assert_called_once_with(case_id="requested", status="pending", session=session)


def test_delivery_forwards_case_with_write_session_and_server_clock(*, monkeypatch):
    service = Mock(return_value=[])
    monkeypatch.setattr(intervention.intervention, "deliver_pending", service)
    session, clock = object(), Mock()
    assert (
        intervention.deliver_interventions(case_id="requested", session=session, now=clock).items
        == []
    )
    service.assert_called_once_with(case_id="requested", session=session, now=clock)
