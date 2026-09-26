import sqlite3
from uuid import uuid4

import pytest
from sqlmodel import select

from normative_conformance.database import read_session
from normative_conformance.errors import EnqueueFailed
from normative_conformance.models.assessment import Assessment
from normative_conformance.models.normative_model import NormativeModelVersion
from normative_conformance.services.assessment.evaluate_case import evaluate_case


def test_detection_time_starts_deadline_and_new_matches_do_not_restart_it(
    *,
    add_observation,
    assess,
    session,
    assessment_queue,
):
    add_observation(start=0, end=0.9, transcript="you are wrong", level=-17.0, received=0)
    first = assess(at=100)
    assert len(first) == 1
    assert first[0].status == "pending"
    assert first[0].evaluated_at_us == 100_000_000
    assert first[0].next_due_at_us == 110_000_000
    assert assessment_queue.queue()[0]["data"]["kind"] == "check_repairs"
    add_observation(start=1, end=1.9, transcript="you are ridiculous", level=-17.0, received=109)
    again = assess(at=109)
    assert [row.model_dump() for row in again] == [row.model_dump() for row in first]
    assert len(session.exec(select(Assessment)).all()) == 1
    assert assessment_queue.qsize() == 1


def test_no_match_creates_no_pending_assessment(*, add_observation, assess, assessment_queue):
    add_observation(start=0, end=1)
    assert assess() == []
    assert assessment_queue.empty()


def test_nonrepairable_match_is_immediate(*, add_observation, assess, session, assessment_queue):
    add_observation(start=0, end=1)
    session.add(
        NormativeModelVersion(
            model_id="immediate",
            version="1",
            name="Immediate",
            type="undesired",
            repairable=False,
            rules_json='[{"rule_id":"always","description":"Always matches","sql":"SELECT 1"}]',
            parameters_json="{}",
        )
    )
    session.commit()
    result = assess()
    assert len(result) == 1
    assert result[0].status == "conformant"
    assert result[0].next_due_at_us is None
    assert assessment_queue.empty()


def test_finalized_match_is_not_repeated_before_repair(*, add_observation, assess, check, session):
    add_observation(start=0, end=0.9, transcript="you are wrong", level=-17.0)
    original = assess()[0]
    final = check()[0]
    assert final.resolves_assessment_id == original.assessment_id
    add_observation(start=2, end=2.9, transcript="you are wrong", level=-17.0, received=111)
    assert assess(at=111)[0].assessment_id == final.assessment_id
    assert len(session.exec(select(Assessment)).all()) == 2


def test_replay_requests_repair_after_enqueue_failure_without_repeating_assessment(
    *, add_observation, engine, scheduler, assessment_queue, received_at, monkeypatch
):
    add_observation(start=0, end=0.9, transcript="you are wrong", level=-17.0)
    evaluation_id = uuid4()
    put = assessment_queue.put

    def fail_enqueue(*, item):
        with read_session(engine=engine) as session:
            assert len(session.exec(select(Assessment)).all()) == 1
        raise sqlite3.OperationalError("Queue failed")

    monkeypatch.setattr(assessment_queue, "put", fail_enqueue)
    with pytest.raises(EnqueueFailed):
        evaluate_case(
            case_id="case",
            evaluation_id=evaluation_id,
            engine=engine,
            now=lambda: received_at,
            scheduler=scheduler,
        )

    monkeypatch.setattr(assessment_queue, "put", put)
    results = evaluate_case(
        case_id="case",
        evaluation_id=evaluation_id,
        engine=engine,
        now=lambda: received_at,
        scheduler=scheduler,
    )
    with read_session(engine=engine) as session:
        assert len(session.exec(select(Assessment)).all()) == 1
    assert len(results) == 1
    assert results[0].evaluation_id == str(evaluation_id)
    assert assessment_queue.get(block=False)["kind"] == "check_repairs"


def test_shutdown_finishes_assessment_without_enqueuing_repair(
    *, add_observation, assess, scheduler, assessment_queue
):
    add_observation(start=0, end=0.9, transcript="you are wrong", level=-17.0)
    scheduler.stopped.set()
    assert assess()[0].status == "pending"
    assert assessment_queue.empty()
