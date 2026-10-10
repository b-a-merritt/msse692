from datetime import datetime
from datetime import timezone
from importlib import import_module
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from normative_conformance.errors import EnqueueFailed
from normative_conformance.errors import ObservationExists
from normative_conformance.errors import StorageUnavailable
from normative_conformance.models.case import CaseLog
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.observation import ObservationInput

module = import_module("normative_conformance.services.observation.ingest")


@pytest.mark.parametrize(
    "existing_case,last_sequence", [(None, None), (CaseLog(case_id="case", created_at_us=0), 7)]
)
def test_assigns_receipt_sequence_and_commits_before_requesting_assessment(
    *, monkeypatch, existing_case, last_sequence
):
    input = ObservationInput(
        case_id="case",
        observation_id="chunk",
        speaker_id="subject",
        start_at="1970-01-01T00:00:00.000001Z",
        end_at="1970-01-01T00:00:00.000009Z",
        transcript=" Hello ",
        signal_level_min=-50,
        signal_level_avg=-30,
        signal_level_max=-10,
    )
    session = Mock(spec=Session)
    session.get.side_effect = [None, existing_case]
    session.exec.return_value.one.return_value = last_sequence
    clock = Mock(return_value=datetime(1970, 1, 1, 0, 0, 1, tzinfo=timezone.utc))
    scheduler = object()
    order = []
    session.connection.side_effect = lambda: order.append("lock")
    clock.side_effect = lambda: (
        order.append("clock"),
        datetime(1970, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
    )[1]
    session.commit.side_effect = lambda: order.append("commit")
    request = Mock(side_effect=lambda **kwargs: order.append("enqueue"))
    monkeypatch.setattr(module, "request_assessment", request)

    result = module.ingest(input=input, session=session, now=clock, scheduler=scheduler)

    assert order == ["lock", "clock", "commit", "enqueue"]
    assert result.sequence == (last_sequence or 0) + 1
    assert result.received_at == datetime(1970, 1, 1, 0, 0, 1, tzinfo=timezone.utc)
    rows = [call.args[0] for call in session.add.call_args_list]
    assert [type(row) for row in rows] == (
        [CaseLog, Observation] if existing_case is None else [Observation]
    )
    assert rows[-1].model_dump() == {
        "case_id": "case",
        "observation_id": "chunk",
        "sequence": result.sequence,
        "received_at_us": 1_000_000,
        "speaker_id": "subject",
        "start_at_us": 1,
        "end_at_us": 9,
        "transcript": " Hello ",
        "signal_level_min": -50,
        "signal_level_avg": -30,
        "signal_level_max": -10,
    }
    request.assert_called_once_with(case_id="case", scheduler=scheduler)
    session.rollback.assert_not_called()


@pytest.mark.parametrize("failure_stage", ["duplicate", "lock", "commit", "enqueue"])
def test_failures_distinguish_rolled_back_work_from_committed_observations(
    *, monkeypatch, failure_stage
):
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
    session = Mock(spec=Session)
    session.get.side_effect = [object() if failure_stage == "duplicate" else None, object()]
    session.exec.return_value.one.return_value = 0
    error = (
        EnqueueFailed(message="Queue unavailable")
        if failure_stage == "enqueue"
        else SQLAlchemyError("Private driver details")
    )
    if failure_stage in {"lock", "commit"}:
        getattr(session, "connection" if failure_stage == "lock" else "commit").side_effect = error
    request = Mock(side_effect=error if failure_stage == "enqueue" else None)
    monkeypatch.setattr(module, "request_assessment", request)
    with pytest.raises(
        ObservationExists
        if failure_stage == "duplicate"
        else EnqueueFailed
        if failure_stage == "enqueue"
        else StorageUnavailable
    ) as caught:
        module.ingest(
            input=input,
            session=session,
            now=lambda: datetime(1970, 1, 1, tzinfo=timezone.utc),
            scheduler=object(),
        )
    if failure_stage == "enqueue":
        assert caught.value.committed_observation.observation_id == "chunk"
        assert (
            str(caught.value)
            == "The observation was stored but its assessment could not be requested"
        )
        assert caught.value.__cause__ is error
        session.commit.assert_called_once()
        session.rollback.assert_not_called()
    else:
        session.rollback.assert_called_once()
        request.assert_not_called()
        if failure_stage == "duplicate":
            assert str(caught.value) == "An observation with this identity already exists"
            session.add.assert_not_called()
        else:
            assert str(caught.value) == "The observation could not be stored"
            assert caught.value.__cause__ is error
