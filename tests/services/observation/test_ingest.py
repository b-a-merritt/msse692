"""Ingestion commits ordered observations before requesting assessment."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from threading import Barrier
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session
from sqlmodel import select

from normative_conformance.database import write_session
from normative_conformance.errors import EnqueueFailed
from normative_conformance.errors import ObservationExists
from normative_conformance.errors import StorageUnavailable
from normative_conformance.models.case import CaseLog
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.services.observation.ingest import ingest


def test_commits_case_and_observation_with_exact_timestamps(
    *, engine, observation_input, received_at, assessment_queue, scheduler
):
    with write_session(engine=engine) as session:
        record = ingest(
            input=observation_input,
            session=session,
            now=lambda: received_at,
            scheduler=scheduler,
        )

    assert record.sequence == 1
    assert record.received_at == received_at
    assert assessment_queue.qsize() == 1
    task = assessment_queue.get(block=False)
    assert task["kind"] == "assess_case"
    assert task["case_id"] == record.case_id
    with Session(bind=engine) as session:
        case = session.get(CaseLog, "case")
        observation = session.get(Observation, ("case", "chunk"))
        assert case is not None
        assert observation is not None
        assert case.created_at_us == observation.received_at_us == 1790413323456789
        assert observation.start_at_us == 1790413200123456
        assert observation.end_at_us == 1790413201654321
        assert observation.sequence == record.sequence
        assert observation.transcript == "  Hello!\n"
        assert observation.speaker_id == "subject"
        assert (
            observation.signal_level_min,
            observation.signal_level_avg,
            observation.signal_level_max,
        ) == (-50.0, -30.0, -10.0)


def test_sequences_follow_arrival_order_within_each_case(
    *, engine, observation_data, received_at, assessment_queue, scheduler
):
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
                scheduler=scheduler,
            )
        sequences.append(record.sequence)
    assert sequences == [1, 2, 1]
    with Session(bind=engine) as session:
        assert session.get(CaseLog, "case").created_at_us == 1790413323456789


@pytest.mark.parametrize("changed_content", [False, True])
def test_duplicates_leave_original_unchanged_and_do_not_consume_sequence(
    *, engine, observation_input, received_at, changed_content, assessment_queue, scheduler
):
    with write_session(engine=engine) as session:
        ingest(
            input=observation_input,
            session=session,
            now=lambda: received_at,
            scheduler=scheduler,
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
                scheduler=scheduler,
            )
        assert not session.in_transaction()
        assert assessment_queue.qsize() == 1
        next_record = ingest(
            input=observation_input.model_copy(update={"observation_id": "next"}),
            session=session,
            now=lambda: received_at + timedelta(seconds=2),
            scheduler=scheduler,
        )
    assert next_record.sequence == 2
    with Session(bind=engine) as session:
        original = session.get(Observation, ("case", "chunk"))
        assert original.transcript == observation_input.transcript
        assert original.received_at_us == 1790413323456789
        assert len(session.exec(select(Observation)).all()) == 2


def test_storage_failure_rolls_back_new_case_and_observation(
    *, engine, observation_input, received_at, assessment_queue, scheduler
):
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
                scheduler=scheduler,
            )
        assert not session.in_transaction()
    assert str(caught.value) == "The observation could not be stored"
    assert isinstance(caught.value.__cause__, IntegrityError)
    assert assessment_queue.empty()
    with Session(bind=engine) as session:
        assert session.exec(select(CaseLog)).all() == []
        assert session.exec(select(Observation)).all() == []


def test_stores_signed_microseconds_without_float_rounding(
    *, engine, observation_data, assessment_queue, scheduler
):
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
            scheduler=scheduler,
        )
    with Session(bind=engine) as session:
        observation = session.get(Observation, ("case", "chunk"))
        assert observation.start_at_us == -2
        assert observation.end_at_us == -1
        assert observation.received_at_us == 16725225600000001


def test_concurrent_ingestion_assigns_distinct_sequences(
    *, engine, observation_input, received_at, assessment_queue, scheduler
):
    ready = Barrier(2, timeout=10)

    def submit(*, observation_id):
        ready.wait()
        with write_session(engine=engine) as session:
            return ingest(
                input=observation_input.model_copy(update={"observation_id": observation_id}),
                session=session,
                now=lambda: received_at,
                scheduler=scheduler,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(submit, observation_id=name) for name in ("first", "second")]
        records = [future.result(timeout=10) for future in futures]
    assert {record.sequence for record in records} == {1, 2}
    assert assessment_queue.qsize() == 1
    with Session(bind=engine) as session:
        assert len(session.exec(select(CaseLog)).all()) == 1
        assert len(session.exec(select(Observation)).all()) == 2


def test_concurrent_duplicates_commit_once(
    *, engine, observation_input, received_at, assessment_queue, scheduler
):
    ready = Barrier(2, timeout=10)

    def submit():
        ready.wait()
        with write_session(engine=engine) as session:
            try:
                ingest(
                    input=observation_input,
                    session=session,
                    now=lambda: received_at,
                    scheduler=scheduler,
                )
            except ObservationExists:
                return "duplicate"
        return "created"

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(submit) for _ in range(2)]
        outcomes = [future.result(timeout=10) for future in futures]
    assert sorted(outcomes) == ["created", "duplicate"]
    assert assessment_queue.qsize() == 1
    with Session(bind=engine) as session:
        observations = session.exec(select(Observation)).all()
        assert len(observations) == 1
        assert observations[0].sequence == 1


def test_observation_is_committed_before_enqueueing(
    *, engine, observation_input, received_at, assessment_queue, scheduler, monkeypatch
):
    original_put = assessment_queue.put

    def put(*, item):
        with Session(bind=engine) as session:
            assert session.get(Observation, (item["case_id"], "chunk")) is not None
        return original_put(item=item)

    monkeypatch.setattr(assessment_queue, "put", put)
    with write_session(engine=engine) as session:
        ingest(
            input=observation_input,
            session=session,
            now=lambda: received_at,
            scheduler=scheduler,
        )
    assert assessment_queue.qsize() == 1


def test_enqueue_failure_keeps_committed_observation(
    *, engine, observation_input, received_at, assessment_queue, scheduler, monkeypatch
):
    monkeypatch.setattr(
        assessment_queue, "put", Mock(side_effect=sqlite3.OperationalError("private queue details"))
    )
    with write_session(engine=engine) as session:
        with pytest.raises(EnqueueFailed) as caught:
            ingest(
                input=observation_input,
                session=session,
                now=lambda: received_at,
                scheduler=scheduler,
            )
        assert not session.in_transaction()

    assert (
        str(caught.value) == "The observation was stored but its assessment could not be requested"
    )
    record = caught.value.committed_observation
    assert record is not None
    assert record.model_dump() == observation_input.model_dump() | {
        "received_at": received_at,
        "sequence": 1,
    }
    assert isinstance(caught.value.__cause__, EnqueueFailed)
    assert isinstance(caught.value.__cause__.__cause__, sqlite3.OperationalError)
    assert assessment_queue.empty()
    with Session(bind=engine) as session:
        assert session.get(CaseLog, record.case_id) is not None
        stored = session.get(Observation, (record.case_id, record.observation_id))
        assert stored is not None
        assert stored.sequence == record.sequence
