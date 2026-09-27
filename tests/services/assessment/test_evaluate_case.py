import sqlite3
from datetime import datetime
from datetime import timezone
from uuid import uuid4

import pytest
from sqlmodel import select

from normative_conformance.database import read_session
from normative_conformance.errors import EnqueueFailed
from normative_conformance.errors import StorageUnavailable
from normative_conformance.models.assessment import Assessment
from normative_conformance.models.normative_model import NormativeModelVersion
from normative_conformance.schemas.assessment import Explanation
from normative_conformance.services.assessment.evaluate_case import evaluate_case


def test_detection_time_starts_deadline_and_new_matches_do_not_restart_it(
    *,
    add_observation,
    assess,
    session,
    assessment_queue,
):
    add_observation(start=0, end=0.9, transcript="stop that right now", level=-17.0, received=0)
    first = assess(at=100)
    assert len(first) == 1
    assert first[0].status == "pending"
    assert first[0].evaluated_at_us == 100_000_000
    assert first[0].next_due_at_us == 110_000_000
    explanation = Explanation.model_validate_json(first[0].explanation_json)
    assert explanation.reason_code == "awaiting_repair"
    assert explanation.rules[0].outcome == "pending"
    assert explanation.rules[0].deadline_at.timestamp() == 110
    assert assessment_queue.queue()[0]["data"]["kind"] == "check_repairs"
    add_observation(start=1, end=1.9, transcript="stop it right now", level=-17.0, received=109)
    again = assess(at=109)
    assert [row.model_dump() for row in again] == [row.model_dump() for row in first]
    assert len(session.exec(select(Assessment)).all()) == 1
    assert assessment_queue.qsize() == 1


def test_no_match_creates_no_pending_assessment(*, add_observation, assess, assessment_queue):
    add_observation(start=0, end=1)
    assert assess() == []
    assert assessment_queue.empty()


def test_no_repair_allowance_confirms_immediately(
    *, add_observation, assess, session, assessment_queue
):
    add_observation(start=0, end=1)
    session.add(
        NormativeModelVersion(
            model_id="immediate",
            version="1",
            name="Immediate",
            type="undesired",
            repair_allowance_us=None,
            rules_json='[{"rule_id":"always","description":"Always matches","sql":"SELECT 1"}]',
            parameters_json="{}",
        )
    )
    session.commit()
    result = assess()
    assert len(result) == 1
    assert result[0].status == "conformant"
    assert result[0].next_due_at_us is None
    explanation = Explanation.model_validate_json(result[0].explanation_json)
    assert explanation.reason_code == "matched"
    assert explanation.rules[0].outcome == "satisfied"
    assert explanation.rules[0].deadline_at is None
    assert assessment_queue.empty()

    repeated = assess(at=101)
    assert [row.assessment_id for row in repeated] == [result[0].assessment_id]
    assert len(session.exec(select(Assessment)).all()) == 1


def test_models_use_their_own_allowance_and_keep_existing_deadlines(
    *, add_observation, assess, check, session
):
    add_observation(start=0, end=1)
    for model_id, allowance in [("short", 2_000_000), ("long", 20_000_000)]:
        session.add(
            NormativeModelVersion(
                model_id=model_id,
                version="1",
                name=model_id,
                type="undesired",
                repair_allowance_us=allowance,
                rules_json='[{"rule_id":"always","description":"Always matches","sql":"SELECT 1"}]',
                parameters_json="{}",
            )
        )
    session.commit()

    originals = {row.model_id: row for row in assess(at=100)}

    assert originals["short"].next_due_at_us == 102_000_000
    assert originals["long"].next_due_at_us == 120_000_000
    for row in originals.values():
        assert row.status == "pending"
        explanation = Explanation.model_validate_json(row.explanation_json)
        assert explanation.rules[0].deadline_at.timestamp() * 1_000_000 == row.next_due_at_us
    assert [row.model_dump() for row in assess(at=101)] == [
        row.model_dump() for row in originals.values()
    ]

    checked = {row.model_id: row for row in check(at=102)}
    assert checked["short"].status == "conformant"
    assert checked["short"].resolves_assessment_id == originals["short"].assessment_id
    assert checked["long"].model_dump() == originals["long"].model_dump()


def test_replay_requests_repair_after_enqueue_failure_without_repeating_assessment(
    *, add_observation, engine, scheduler, assessment_queue, received_at, monkeypatch
):
    add_observation(start=0, end=0.9, transcript="stop that right now", level=-17.0)
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
    add_observation(start=0, end=0.9, transcript="stop that right now", level=-17.0)
    scheduler.stopped.set()
    assert assess()[0].status == "pending"
    assert assessment_queue.empty()


def test_replayed_evaluation_preserves_its_original_results(*, add_observation, assess):
    add_observation(start=0, end=0.9, transcript="stop that right now", level=-17.0)
    evaluation_id = uuid4()
    original = assess(evaluation_id=evaluation_id)
    add_observation(start=1, end=32, received=101)

    replayed = assess(at=102, evaluation_id=evaluation_id)

    assert [row.model_dump() for row in replayed] == [row.model_dump() for row in original]
    assert replayed[0].through_sequence == 1
    assert {row.model_id for row in assess(at=102)} == {
        "high_intensity_address",
        "extended_turn",
    }


def test_failed_assessment_rolls_back_all_models_before_requesting_repairs(
    *, add_observation, assess, engine, assessment_queue
):
    add_observation(start=0, end=0.9, transcript="stop that right now", level=-17.0)
    add_observation(start=1, end=32)
    # Extended turn is stored first; fail the second model's write.
    with engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE TRIGGER fail_assessment BEFORE INSERT ON assessment
            WHEN NEW.model_id = 'high_intensity_address'
            BEGIN SELECT RAISE(ABORT, 'Assessment write failed'); END
        """)

    with pytest.raises(StorageUnavailable, match="The case could not be assessed"):
        assess()

    with read_session(engine=engine) as session:
        assert session.exec(select(Assessment)).all() == []
    assert assessment_queue.empty()


def test_new_matches_share_the_case_evaluation_time(*, add_observation, engine, scheduler):
    add_observation(start=0, end=0.9, transcript="stop that right now", level=-17.0)
    add_observation(start=1, end=32)
    times = iter([100])

    results = evaluate_case(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        scheduler=scheduler,
        now=lambda: datetime.fromtimestamp(next(times), timezone.utc),
    )

    assert [(row.model_id, row.evaluated_at_us, row.next_due_at_us) for row in results] == [
        ("extended_turn", 100_000_000, 110_000_000),
        ("high_intensity_address", 100_000_000, 110_000_000),
    ]


def test_models_share_one_subject_lookup(*, add_observation, assess, subject_config_reads):
    add_observation(start=0, end=0.9, transcript="stop that right now", level=-17.0)
    add_observation(start=1, end=32)

    assert len(assess()) == 2
    assert len(subject_config_reads) == 1


def test_replay_preserves_pending_result_after_resolution(*, add_observation, assess, check):
    add_observation(start=0, end=0.9, transcript="stop that right now", level=-17.0)
    evaluation_id = uuid4()
    original = assess(evaluation_id=evaluation_id)[0]
    final = check()[0]
    assert final.resolves_assessment_id == original.assessment_id

    replayed = assess(at=111, evaluation_id=evaluation_id)

    assert [row.model_dump() for row in replayed] == [original.model_dump()]
