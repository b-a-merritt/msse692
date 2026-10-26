from datetime import datetime
from datetime import timezone
from importlib import import_module
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from normative_conformance.errors import ObservationExists
from normative_conformance.errors import StorageUnavailable
from normative_conformance.models.case import CaseLog
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.observation import ObservationInput

module = import_module("normative_conformance.services.observation.ingest")


@pytest.mark.parametrize(
    "existing_case,last_sequence",
    [
        (None, None),
        (CaseLog(case_id="case", created_at_us=0), 7),
        (CaseLog(case_id="case", created_at_us=0, target_speaker_order=2), 2),
    ],
)
def test_assigns_receipt_sequence_and_commits(*, monkeypatch, existing_case, last_sequence):
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
    session.get.side_effect = lambda model, key: existing_case if model is CaseLog else None
    session.exec.return_value.one.return_value = last_sequence
    session.exec.return_value.all.return_value = ["A", "A", "B"]
    clock = Mock(return_value=datetime(1970, 1, 1, 0, 0, 1, tzinfo=timezone.utc))
    order = []
    session.connection.side_effect = lambda: order.append("lock")
    clock.side_effect = lambda: (
        order.append("clock"),
        datetime(1970, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
    )[1]
    session.commit.side_effect = lambda: order.append("commit")

    result = module.ingest(input=input, session=session, now=clock)

    assert order.index("lock") < order.index("clock")
    assert result.sequence == (last_sequence or 0) + 1
    assert result.received_at == datetime(1970, 1, 1, 0, 0, 1, tzinfo=timezone.utc)
    rows = [call.args[0] for call in session.add.call_args_list]
    if existing_case is None:
        case = next(row for row in rows if isinstance(row, CaseLog))
        assert case.case_id == "case"
        assert case.created_at_us == 1_000_000
    observation = next(row for row in rows if isinstance(row, Observation))
    assert observation.model_dump() == {
        "case_id": "case",
        "observation_id": "chunk",
        "sequence": result.sequence,
        "received_at_us": 1_000_000,
        "updated_at_us": 1_000_000,
        "speaker_id": "subject",
        "start_at_us": 1,
        "end_at_us": 9,
        "transcript": " Hello ",
        "signal_level_min": -50,
        "signal_level_avg": -30,
        "signal_level_max": -10,
    }
    if existing_case is not None and existing_case.target_speaker_order == 2:
        assert existing_case.target_speaker_id == "B"
        assert existing_case.target_revision == 1
    session.rollback.assert_not_called()


@pytest.mark.parametrize("failure_stage", ["duplicate", "lock", "commit"])
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
    session.get.side_effect = lambda model, key: (
        CaseLog(case_id="case", created_at_us=0)
        if model is CaseLog
        else object()
        if failure_stage == "duplicate"
        else None
    )
    session.exec.return_value.one.return_value = 0
    error = SQLAlchemyError("Private driver details")
    if failure_stage in {"lock", "commit"}:
        getattr(session, "connection" if failure_stage == "lock" else "commit").side_effect = error
    with pytest.raises(
        ObservationExists if failure_stage == "duplicate" else StorageUnavailable
    ) as caught:
        module.ingest(
            input=input,
            session=session,
            now=lambda: datetime(1970, 1, 1, tzinfo=timezone.utc),
        )
    session.rollback.assert_called_once()
    if failure_stage == "duplicate":
        assert str(caught.value) == "An observation with this identity already exists"
        session.add.assert_not_called()
    else:
        assert str(caught.value) == "The observation could not be stored"
        assert caught.value.__cause__ is error


def test_staging_leaves_transaction_to_caller(monkeypatch):
    case = CaseLog(case_id="case", created_at_us=0)
    session = Mock(spec=Session)
    session.get.side_effect = lambda model, key: case if model is CaseLog else None
    session.exec.return_value.one.return_value = 3
    input = ObservationInput(
        case_id="case",
        observation_id="chunk",
        speaker_id="A",
        start_at="1970-01-01T00:00:00Z",
        end_at="1970-01-01T00:00:01Z",
        transcript="Hello",
        signal_level_min=-50,
        signal_level_avg=-30,
        signal_level_max=-10,
    )
    record = module.stage_observation(
        input=input,
        session=session,
        now=lambda: datetime(1970, 1, 1, 0, 0, 0, 90, tzinfo=timezone.utc),
    )
    assert record.sequence == 4
    assert record.received_at == record.updated_at
    assert record.updated_at.microsecond == 90
    row = session.add.call_args.args[0]
    assert row.observation_id == "chunk"
    assert row.sequence == 4
    assert row.received_at_us == row.updated_at_us == 90
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_staging_propagates_flush_failures_for_the_caller_to_roll_back():
    session = Mock(spec=Session)
    session.get.side_effect = lambda model, key: (
        CaseLog(case_id="case", created_at_us=0) if model is CaseLog else None
    )
    session.exec.return_value.one.return_value = 0
    error = SQLAlchemyError("Flush failed")
    session.flush.side_effect = error
    input = ObservationInput(
        case_id="case",
        observation_id="chunk",
        speaker_id="A",
        start_at="1970-01-01T00:00:00Z",
        end_at="1970-01-01T00:00:01Z",
        transcript="Hello",
        signal_level_min=-50,
        signal_level_avg=-30,
        signal_level_max=-10,
    )
    with pytest.raises(SQLAlchemyError) as caught:
        module.stage_observation(
            input=input, session=session, now=lambda: datetime(1970, 1, 1, tzinfo=timezone.utc)
        )
    assert caught.value is error
    session.commit.assert_not_called()
    session.rollback.assert_not_called()
