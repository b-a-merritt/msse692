"""Ingestion commits ordered observations for database polling."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from threading import Barrier

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session
from sqlmodel import select

from normative_conformance.database import read_session
from normative_conformance.database import write_session
from normative_conformance.errors import ObservationExists
from normative_conformance.errors import StorageUnavailable
from normative_conformance.models.case import CaseLog
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.services.observation.ingest import ingest


def test_commits_case_and_observation_with_exact_timestamps(*, engine):
    observation_data = {
        "case_id": "case",
        "observation_id": "chunk",
        "speaker_id": "subject",
        "start_at": "2026-09-26T12:00:00.123456+03:00",
        "end_at": "2026-09-26T12:00:01.654321+03:00",
        "transcript": "  Hello!\n",
        "signal_level_min": -50.0,
        "signal_level_avg": -30.0,
        "signal_level_max": -10.0,
    }
    observation_input = ObservationInput.model_validate(observation_data)
    received_at = datetime(2026, 9, 26, 9, 2, 3, 456_789, tzinfo=timezone.utc)

    with write_session(engine=engine) as session:
        record = ingest(
            input=observation_input,
            session=session,
            now=lambda: received_at,
        )

    assert record.sequence == 1
    assert record.received_at == received_at
    with Session(bind=engine) as session:
        case = session.get(CaseLog, "case")
        observation = session.exec(
            select(Observation).where(
                Observation.case_id == "case", Observation.observation_id == "chunk"
            )
        ).one_or_none()
        assert case is not None
        assert observation is not None
        assert case.created_at_us == observation.received_at_us == 1_790_413_323_456_789
        assert observation.start_at_us == 1_790_413_200_123_456
        assert observation.end_at_us == 1_790_413_201_654_321
        assert observation.sequence == record.sequence
        assert observation.transcript == "  Hello!\n"
        assert observation.speaker_id == "subject"
        assert (
            observation.signal_level_min,
            observation.signal_level_avg,
            observation.signal_level_max,
        ) == (-50.0, -30.0, -10.0)


def test_sequences_follow_arrival_order_within_each_case(*, engine):
    observation_data = {
        "case_id": "case",
        "observation_id": "chunk",
        "speaker_id": "subject",
        "start_at": "2026-09-26T12:00:00.123456+03:00",
        "end_at": "2026-09-26T12:00:01.654321+03:00",
        "transcript": "  Hello!\n",
        "signal_level_min": -50.0,
        "signal_level_avg": -30.0,
        "signal_level_max": -10.0,
    }
    received_at = datetime(2026, 9, 26, 9, 2, 3, 456_789, tzinfo=timezone.utc)

    inputs = [
        observation_data,
        observation_data
        | {
            "observation_id": "earlier-source",
            "start_at": "2026-09-25T09:00:00Z",
            "end_at": "2026-09-25T09:00:01Z",
        },
        observation_data | {"case_id": "other"},
    ]
    sequences = []
    for offset, values in enumerate(inputs):
        timestamp = received_at + timedelta(seconds=offset)
        with write_session(engine=engine) as session:
            record = ingest(
                input=ObservationInput.model_validate(values),
                session=session,
                now=lambda timestamp=timestamp: timestamp,
            )
        sequences.append(record.sequence)
    assert sequences == [1, 2, 1]
    with Session(bind=engine) as session:
        assert session.get(CaseLog, "case").created_at_us == 1_790_413_323_456_789


@pytest.mark.parametrize("changed_content", [False, True])
def test_duplicates_leave_original_unchanged_and_do_not_consume_sequence(
    *, engine, changed_content
):
    observation_data = {
        "case_id": "case",
        "observation_id": "chunk",
        "speaker_id": "subject",
        "start_at": "2026-09-26T12:00:00.123456+03:00",
        "end_at": "2026-09-26T12:00:01.654321+03:00",
        "transcript": "  Hello!\n",
        "signal_level_min": -50.0,
        "signal_level_avg": -30.0,
        "signal_level_max": -10.0,
    }
    observation_input = ObservationInput.model_validate(observation_data)
    received_at = datetime(2026, 9, 26, 9, 2, 3, 456_789, tzinfo=timezone.utc)

    with write_session(engine=engine) as session:
        ingest(
            input=observation_input,
            session=session,
            now=lambda: received_at,
        )
    duplicate = observation_input.model_copy(
        update={"transcript": "Different content"} if changed_content else {}
    )
    with write_session(engine=engine) as session:
        with pytest.raises(
            ObservationExists, match="An observation with this identity already exists"
        ):
            ingest(
                input=duplicate,
                session=session,
                now=lambda: received_at + timedelta(seconds=1),
            )
        assert not session.in_transaction()
        next_record = ingest(
            input=observation_input.model_copy(update={"observation_id": "next"}),
            session=session,
            now=lambda: received_at + timedelta(seconds=2),
        )
    assert next_record.sequence == 2
    with Session(bind=engine) as session:
        original = session.exec(
            select(Observation).where(
                Observation.case_id == "case", Observation.observation_id == "chunk"
            )
        ).one_or_none()
        assert original.transcript == observation_input.transcript
        assert original.received_at_us == 1_790_413_323_456_789
        assert len(session.exec(select(Observation)).all()) == 2


def test_storage_failure_rolls_backnew_case_and_observation(*, engine):
    observation_data = {
        "case_id": "case",
        "observation_id": "chunk",
        "speaker_id": "subject",
        "start_at": "2026-09-26T12:00:00.123456+03:00",
        "end_at": "2026-09-26T12:00:01.654321+03:00",
        "transcript": "  Hello!\n",
        "signal_level_min": -50.0,
        "signal_level_avg": -30.0,
        "signal_level_max": -10.0,
    }
    observation_input = ObservationInput.model_validate(observation_data)
    received_at = datetime(2026, 9, 26, 9, 2, 3, 456_789, tzinfo=timezone.utc)

    with engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE TRIGGER fail_ingestion BEFORE INSERT ON observation
            BEGIN SELECT RAISE(ABORT, 'internal storage failure'); END
        """)
    with write_session(engine=engine) as session:
        with pytest.raises(StorageUnavailable) as caught:
            ingest(
                input=observation_input,
                session=session,
                now=lambda: received_at,
            )
        assert not session.in_transaction()
    assert str(caught.value) == "The observation could not be stored"
    assert isinstance(caught.value.__cause__, IntegrityError)
    with Session(bind=engine) as session:
        assert session.exec(select(CaseLog)).all() == []
        assert session.exec(select(Observation)).all() == []


def test_stores_signed_microseconds_without_float_rounding(*, engine):
    observation_data = {
        "case_id": "case",
        "observation_id": "chunk",
        "speaker_id": "subject",
        "start_at": "2026-09-26T12:00:00.123456+03:00",
        "end_at": "2026-09-26T12:00:01.654321+03:00",
        "transcript": "  Hello!\n",
        "signal_level_min": -50.0,
        "signal_level_avg": -30.0,
        "signal_level_max": -10.0,
    }

    input = ObservationInput.model_validate(
        observation_data
        | {
            "start_at": "1969-12-31T23:59:59.999998Z",
            "end_at": "1969-12-31T23:59:59.999999Z",
        }
    )
    with write_session(engine=engine) as session:
        ingest(
            input=input,
            session=session,
            now=lambda: datetime(2500, 1, 1, 0, 0, 0, 1, tzinfo=timezone.utc),
        )
    with Session(bind=engine) as session:
        observation = session.exec(
            select(Observation).where(
                Observation.case_id == "case", Observation.observation_id == "chunk"
            )
        ).one_or_none()
        assert observation.start_at_us == -2
        assert observation.end_at_us == -1
        assert observation.received_at_us == 16_725_225_600_000_001


def test_concurrent_ingestion_assigns_distinct_sequences(*, engine):
    observation_data = {
        "case_id": "case",
        "observation_id": "chunk",
        "speaker_id": "subject",
        "start_at": "2026-09-26T12:00:00.123456+03:00",
        "end_at": "2026-09-26T12:00:01.654321+03:00",
        "transcript": "  Hello!\n",
        "signal_level_min": -50.0,
        "signal_level_avg": -30.0,
        "signal_level_max": -10.0,
    }
    observation_input = ObservationInput.model_validate(observation_data)
    received_at = datetime(2026, 9, 26, 9, 2, 3, 456_789, tzinfo=timezone.utc)

    ready = Barrier(2, timeout=10)

    def submit(*, observation_id):
        ready.wait()
        with write_session(engine=engine) as session:
            return ingest(
                input=observation_input.model_copy(update={"observation_id": observation_id}),
                session=session,
                now=lambda: received_at,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(submit, observation_id=name) for name in ("first", "second")]
        records = [future.result(timeout=10) for future in futures]
    assert {record.sequence for record in records} == {1, 2}
    with Session(bind=engine) as session:
        assert len(session.exec(select(CaseLog)).all()) == 1
        assert len(session.exec(select(Observation)).all()) == 2


def test_concurrent_duplicates_commit_once(*, engine):
    observation_data = {
        "case_id": "case",
        "observation_id": "chunk",
        "speaker_id": "subject",
        "start_at": "2026-09-26T12:00:00.123456+03:00",
        "end_at": "2026-09-26T12:00:01.654321+03:00",
        "transcript": "  Hello!\n",
        "signal_level_min": -50.0,
        "signal_level_avg": -30.0,
        "signal_level_max": -10.0,
    }
    observation_input = ObservationInput.model_validate(observation_data)
    received_at = datetime(2026, 9, 26, 9, 2, 3, 456_789, tzinfo=timezone.utc)

    ready = Barrier(2, timeout=10)

    def submit():
        ready.wait()
        with write_session(engine=engine) as session:
            try:
                ingest(
                    input=observation_input,
                    session=session,
                    now=lambda: received_at,
                )
            except ObservationExists:
                return "duplicate"
        return "created"

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(submit) for _ in range(2)]
        outcomes = [future.result(timeout=10) for future in futures]
    assert sorted(outcomes) == ["created", "duplicate"]
    with Session(bind=engine) as session:
        observations = session.exec(select(Observation)).all()
        assert len(observations) == 1
        assert observations[0].sequence == 1


@pytest.mark.parametrize("commit", [False, True])
def test_staged_observations_and_case_share_one_transaction(engine, commit):
    from normative_conformance.services.observation.ingest import stage_observation

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
    second = ObservationInput(
        case_id="capture",
        observation_id="two",
        speaker_id="B",
        start_at="1970-01-01T00:00:01Z",
        end_at="1970-01-01T00:00:02Z",
        transcript="Hi",
        signal_level_min=-50,
        signal_level_avg=-30,
        signal_level_max=-10,
    )
    with write_session(engine=engine) as session:
        one = stage_observation(
            input=first,
            session=session,
            now=lambda: datetime(1970, 1, 1, 0, 0, 3, tzinfo=timezone.utc),
        )
        two = stage_observation(
            input=second,
            session=session,
            now=lambda: datetime(1970, 1, 1, 0, 0, 3, tzinfo=timezone.utc),
        )
        assert (one.sequence, two.sequence) == (1, 2)
        assert one.received_at == one.updated_at == two.updated_at
        if commit:
            session.commit()
    with read_session(engine=engine) as session:
        case = session.get(CaseLog, "capture")
        row = session.exec(
            select(Observation).where(
                Observation.case_id == "capture", Observation.observation_id == "one"
            )
        ).one_or_none()
        other = session.exec(
            select(Observation).where(
                Observation.case_id == "capture", Observation.observation_id == "two"
            )
        ).one_or_none()
        if commit:
            assert case.created_at_us == 3_000_000
            assert row.received_at_us == 3_000_000
            assert other.sequence == 2
        else:
            assert case is row is other is None
