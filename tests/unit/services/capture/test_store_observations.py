from datetime import UTC
from datetime import datetime
from unittest.mock import MagicMock
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from normative_conformance.errors import CaptureFailure
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.services.capture import store_observations as module


def test_commits_whole_turn(monkeypatch):
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
    context = MagicMock()
    context.__enter__.return_value = session
    monkeypatch.setattr(module, "write_session", Mock(return_value=context))
    stages = []
    monkeypatch.setattr(module, "stage_observation", lambda **kw: stages.append(kw["input"]))
    committed = []
    session.commit.side_effect = lambda: committed.extend(stages)

    module.store_observations(
        case_id="case",
        observations=[observation, other],
        engine=object(),
        now=lambda: datetime(2026, 10, 26, tzinfo=UTC),
    )
    assert committed == [observation, other]


@pytest.mark.parametrize("stage,expected", [("write", "storageUnavailable")])
def test_write_failure_is_reported(monkeypatch, stage, expected):
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
    context = MagicMock()
    context.__enter__.return_value = session
    monkeypatch.setattr(module, "write_session", Mock(return_value=context))
    insert = Mock(side_effect=SQLAlchemyError("private") if stage == "write" else None)
    monkeypatch.setattr(module, "stage_observation", insert)
    with pytest.raises(CaptureFailure) as caught:
        module.store_observations(
            case_id="case",
            observations=[observation],
            engine=object(),
            now=lambda: datetime(1970, 1, 1, tzinfo=UTC),
        )
    assert caught.value.code == expected
    session.commit.assert_not_called()


def test_no_observations_requires_no_storage(monkeypatch):
    write = Mock(side_effect=AssertionError("Must not open storage"))
    monkeypatch.setattr(module, "write_session", write)
    module.store_observations(
        case_id="case",
        observations=[],
        engine=object(),
        now=lambda: datetime(1970, 1, 1, tzinfo=UTC),
    )
    write.assert_not_called()
