from datetime import UTC
from datetime import datetime

import pytest
from sqlmodel import select

from normative_conformance.database import read_session
from normative_conformance.database import write_session
from normative_conformance.errors import CaptureFailure
from normative_conformance.models.case import ConversationCase
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.services.capture.store_observations import store_observations
from normative_conformance.services.case.target import current_assignment


def test_turn_is_committed_in_order_and_resolves_target(engine):
    first = ObservationInput(
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
    second = first.model_copy(
        update={
            "observation_id": "two",
            "speaker_id": "B",
            "transcript": "Yes",
            "start_at": datetime(2026, 10, 26, 0, 0, 1, tzinfo=UTC),
            "end_at": datetime(2026, 10, 26, 0, 0, 2, tzinfo=UTC),
        }
    )
    with write_session(engine=engine) as session:
        session.add(ConversationCase(case_id="case", created_at_us=0, target_speaker_order=2))
        session.commit()
    store_observations(
        case_id="case",
        observations=[first, second],
        engine=engine,
        now=lambda: datetime(2026, 10, 26, 0, 0, 3, tzinfo=UTC),
    )
    with read_session(engine=engine) as session:
        rows = session.exec(select(Observation).order_by(Observation.sequence)).all()
        assert [(row.observation_id, row.sequence) for row in rows] == [("one", 1), ("two", 2)]
        assert all(row.received_at_us is not None for row in rows)
        assignment = current_assignment(case_id="case", session=session)
        assert (assignment.target_revision, assignment.speaker_id) == (1, "B")


def test_second_run_failure_rolls_back_whole_turn_and_target(engine):
    first = ObservationInput(
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
    second = first.model_copy(
        update={"observation_id": "two", "speaker_id": "B", "transcript": "Yes"}
    )
    with write_session(engine=engine) as session:
        session.add(ConversationCase(case_id="case", created_at_us=0, target_speaker_order=1))
        session.commit()
    with engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE TRIGGER reject_second BEFORE INSERT ON observation
            WHEN NEW.observation_id = 'two'
            BEGIN SELECT RAISE(ABORT, 'cannot write'); END
        """)
    with pytest.raises(CaptureFailure) as caught:
        store_observations(
            case_id="case",
            observations=[first, second],
            engine=engine,
            now=lambda: datetime(2026, 10, 26, tzinfo=UTC),
        )
    assert caught.value.code == "storageUnavailable"
    with read_session(engine=engine) as session:
        assert session.exec(select(Observation)).all() == []
        assert current_assignment(case_id="case", session=session) is None
