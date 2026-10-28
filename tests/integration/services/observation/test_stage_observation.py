"""Staged observations commit only with the caller's transaction."""

from datetime import UTC
from datetime import datetime

from sqlmodel import select

from normative_conformance.database import read_session
from normative_conformance.database import write_session
from normative_conformance.models.case import ConversationCase
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.services.observation.stage_observation import stage_observation


def test_staged_observations_and_new_case_commit_together(engine):
    first = ObservationInput(
        case_id="capture",
        observation_id="one",
        speaker_id="A",
        start_at="1970-01-01T00:00:00Z",
        end_at="1970-01-01T00:00:01Z",
        transcript="Hello",
        signal_level_min=-50,
        signal_level_avg=-30,
        signal_level_max=-10,
    )
    second = first.model_copy(update={"observation_id": "two", "speaker_id": "B"})
    with write_session(engine=engine) as session:
        for row in (first, second):
            stage_observation(
                input=row,
                session=session,
                now=lambda: datetime(1970, 1, 1, 0, 0, 3, tzinfo=UTC),
            )
        session.commit()
    with read_session(engine=engine) as session:
        assert session.get(ConversationCase, "capture").created_at_us == 3_000_000
        assert session.exec(
            select(Observation.observation_id, Observation.sequence, Observation.received_at_us)
            .where(Observation.case_id == "capture")
            .order_by(Observation.sequence)
        ).all() == [("one", 1, 3_000_000), ("two", 2, 3_000_000)]


def test_uncommitted_staged_observations_leave_no_case(engine):
    with write_session(engine=engine) as session:
        stage_observation(
            input=ObservationInput(
                case_id="capture",
                observation_id="one",
                speaker_id="A",
                start_at="1970-01-01T00:00:00Z",
                end_at="1970-01-01T00:00:01Z",
                transcript="Hello",
                signal_level_min=-50,
                signal_level_avg=-30,
                signal_level_max=-10,
            ),
            session=session,
            now=lambda: datetime(1970, 1, 1, 0, 0, 3, tzinfo=UTC),
        )
    with read_session(engine=engine) as session:
        assert session.get(ConversationCase, "capture") is None
        assert session.exec(select(Observation)).all() == []
