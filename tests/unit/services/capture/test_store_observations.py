from datetime import datetime
from datetime import timezone
from unittest.mock import MagicMock
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from normative_conformance.errors import CaptureFailure
from normative_conformance.errors import EnqueueFailed
from normative_conformance.models.case import CaseLog
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.services.capture import store_observations as module


@pytest.mark.parametrize("target", [None, "B"])
def test_commits_whole_turn_before_scheduling_and_waits_for_target(monkeypatch, target):
    observation = ObservationInput(
        case_id="case",
        observation_id="one",
        speaker_id="A",
        start_at="2026-10-26T00:00:00Z",
        end_at="2026-10-26T00:00:01Z",
        transcript="Hello",
        signal_level_min=-50,
        signal_level_avg=-30,
        signal_level_max=-10,
    )
    other = observation.model_copy(
        update={"observation_id": "two", "speaker_id": "B", "transcript": "Yes"}
    )
    session = Mock(spec=Session)
    session.get.return_value = CaseLog(case_id="case", created_at_us=0, target_speaker_id=target)
    context = MagicMock()
    context.__enter__.return_value = session
    monkeypatch.setattr(module, "write_session", Mock(return_value=context))
    stages = []
    monkeypatch.setattr(module, "stage_observation", lambda **kw: stages.append(kw["input"]))
    committed = []
    session.commit.side_effect = lambda: committed.extend(stages)

    def schedule(**kwargs):
        assert committed == [observation, other]

    request = Mock(side_effect=schedule)
    monkeypatch.setattr(module, "request_assessment", request)
    scheduler = object()
    module.store_observations(
        case_id="case",
        observations=[observation, other],
        engine=object(),
        now=lambda: datetime(2026, 10, 26, tzinfo=timezone.utc),
        scheduler=scheduler,
    )
    assert committed == [observation, other]
    if target is None:
        request.assert_not_called()
    else:
        request.assert_called_once_with(case_id="case", scheduler=scheduler)


@pytest.mark.parametrize(
    "stage,expected", [("write", "storageUnavailable"), ("schedule", "assessmentUnavailable")]
)
def test_write_and_scheduling_failures_are_distinct(monkeypatch, stage, expected):
    observation = ObservationInput(
        case_id="case",
        observation_id="one",
        speaker_id="A",
        start_at="1970-01-01T00:00:00Z",
        end_at="1970-01-01T00:00:01Z",
        transcript="Hello",
        signal_level_min=-50,
        signal_level_avg=-30,
        signal_level_max=-10,
    )
    session = Mock(spec=Session)
    session.get.return_value = CaseLog(case_id="case", created_at_us=0, target_speaker_id="A")
    context = MagicMock()
    context.__enter__.return_value = session
    monkeypatch.setattr(module, "write_session", Mock(return_value=context))
    insert = Mock(side_effect=SQLAlchemyError("private") if stage == "write" else None)
    request = Mock(side_effect=EnqueueFailed(message="private"))
    monkeypatch.setattr(module, "stage_observation", insert)
    monkeypatch.setattr(module, "request_assessment", request)
    with pytest.raises(CaptureFailure) as caught:
        module.store_observations(
            case_id="case",
            observations=[observation],
            engine=object(),
            now=lambda: datetime(1970, 1, 1, tzinfo=timezone.utc),
            scheduler=object(),
        )
    assert caught.value.code == expected
    if stage == "write":
        session.commit.assert_not_called()
        request.assert_not_called()
    else:
        session.commit.assert_called_once()


def test_no_observations_requires_no_storage(monkeypatch):
    write = Mock(side_effect=AssertionError("Must not open storage"))
    monkeypatch.setattr(module, "write_session", write)
    module.store_observations(
        case_id="case",
        observations=[],
        engine=object(),
        now=lambda: datetime(1970, 1, 1, tzinfo=timezone.utc),
        scheduler=object(),
    )
    write.assert_not_called()
