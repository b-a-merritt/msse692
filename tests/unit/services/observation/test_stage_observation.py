from datetime import UTC
from datetime import datetime
from importlib import import_module
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from normative_conformance.models.case import ConversationCase
from normative_conformance.schemas.observation import ObservationInput

module = import_module("normative_conformance.services.observation.stage_observation")


def test_staging_leaves_transaction_to_caller(monkeypatch):
    case = ConversationCase(case_id="case", created_at_us=0)
    session = Mock(spec=Session)
    session.get.return_value = case
    session.exec.return_value.first.return_value = None
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
        now=lambda: datetime(1970, 1, 1, 0, 0, 0, 90, tzinfo=UTC),
    )
    assert record.sequence == 4
    assert record.received_at.microsecond == 90
    row = session.add.call_args.args[0]
    assert row.observation_id == "chunk"
    assert row.sequence == 4
    assert row.received_at_us == 90
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_staging_propagates_flush_failures_for_the_caller_to_roll_back():
    session = Mock(spec=Session)
    session.get.return_value = ConversationCase(case_id="case", created_at_us=0)
    session.exec.return_value.first.return_value = None
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
            input=input, session=session, now=lambda: datetime(1970, 1, 1, tzinfo=UTC)
        )
    assert caught.value is error
    session.commit.assert_not_called()
    session.rollback.assert_not_called()
