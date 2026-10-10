from unittest.mock import Mock

from normative_conformance.routes import observation
from normative_conformance.schemas.observation import ObservationInput


def test_submission_delegates_the_complete_workflow_to_ingestion(*, monkeypatch):
    input = ObservationInput(
        case_id="case",
        observation_id="chunk",
        speaker_id="subject",
        start_at="1970-01-01T00:00:00Z",
        end_at="1970-01-01T00:00:01Z",
        transcript="hello",
        signal_level_min=-50,
        signal_level_avg=-30,
        signal_level_max=-10,
    )
    session, clock, scheduler = object(), Mock(), object()
    service = Mock(return_value=object())
    monkeypatch.setattr(observation.observation, "ingest", service)
    assert (
        observation.submit_observation(input=input, session=session, now=clock, scheduler=scheduler)
        is service.return_value
    )
    service.assert_called_once_with(input=input, session=session, now=clock, scheduler=scheduler)
    clock.assert_not_called()


def test_listing_scopes_results_to_the_requested_case(*, monkeypatch):
    service = Mock(return_value=[])
    monkeypatch.setattr(observation.observation, "list_observations", service)
    session = object()
    assert observation.list_observations(case_id="requested", session=session).items == []
    service.assert_called_once_with(case_id="requested", session=session)
