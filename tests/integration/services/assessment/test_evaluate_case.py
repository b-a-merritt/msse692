import sqlite3
from datetime import datetime
from datetime import timezone
from itertools import count
from uuid import uuid4

import pytest
from sqlmodel import select

from normative_conformance import models
from normative_conformance.database import read_session
from normative_conformance.errors import EnqueueFailed
from normative_conformance.errors import StorageUnavailable
from normative_conformance.models.assessment import Assessment
from normative_conformance.models.normative_model import NormativeModelVersion
from normative_conformance.schemas.assessment import Explanation
from normative_conformance.services.assessment.check_repairs import check_repairs
from normative_conformance.services.assessment.evaluate_case import evaluate_case
from normative_conformance.services.model.list_models import list_models
from normative_conformance.services.scheduler.state import SchedulerState

from ...storage import persist


def test_detection_time_starts_deadline_and_new_matches_do_not_restart_it(
    *, session, engine, assessment_queue
):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)
    scheduler = SchedulerState(queue=assessment_queue)

    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=1_500_000,
            received_at_us=0,
            transcript="stop that right now please",
            signal_level_min=-60.0,
            signal_level_avg=-16.0,
            signal_level_max=0.0,
        ),
    )
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    first = evaluate_case(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        now=lambda: datetime.fromtimestamp(100, timezone.utc),
        scheduler=scheduler,
        models=evaluation_models,
    )
    assert len(first) == 1
    assert first[0].status == "pending"
    assert first[0].evaluated_at_us == 100_000_000
    assert first[0].next_due_at_us == 110_000_000
    explanation = Explanation.model_validate_json(first[0].explanation_json)
    assert explanation.reason_code == "awaiting_repair"
    assert explanation.rules[0].outcome == "pending"
    assert explanation.rules[0].deadline_at.timestamp() == 110
    assert assessment_queue.queue()[0]["data"]["kind"] == "check_repairs"
    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=1_000_000,
            end_at_us=2_500_000,
            received_at_us=109_000_000,
            transcript="stop it right now please",
            signal_level_min=-60.0,
            signal_level_avg=-16.0,
            signal_level_max=0.0,
        ),
    )
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    again = evaluate_case(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        now=lambda: datetime.fromtimestamp(109, timezone.utc),
        scheduler=scheduler,
        models=evaluation_models,
    )
    assert [row.model_dump() for row in again] == [row.model_dump() for row in first]
    assert len(session.exec(select(Assessment)).all()) == 1
    assert assessment_queue.qsize() == 1


def test_no_match_creates_no_pending_assessment(*, session, engine, assessment_queue):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)
    scheduler = SchedulerState(queue=assessment_queue)

    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=1_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    assert (
        evaluate_case(
            case_id="case",
            evaluation_id=uuid4(),
            engine=engine,
            now=lambda: datetime.fromtimestamp(100, timezone.utc),
            scheduler=scheduler,
            models=evaluation_models,
        )
        == []
    )
    assert assessment_queue.empty()


def test_no_repair_allowance_confirms_immediately(*, session, engine, assessment_queue):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)
    scheduler = SchedulerState(queue=assessment_queue)

    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=1_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
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
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    result = evaluate_case(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        now=lambda: datetime.fromtimestamp(100, timezone.utc),
        scheduler=scheduler,
        models=evaluation_models,
    )
    assert len(result) == 1
    assert result[0].status == "conformant"
    assert result[0].next_due_at_us is None
    explanation = Explanation.model_validate_json(result[0].explanation_json)
    assert explanation.reason_code == "matched"
    assert explanation.rules[0].outcome == "satisfied"
    assert explanation.rules[0].deadline_at is None
    assert assessment_queue.empty()

    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    repeated = evaluate_case(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        now=lambda: datetime.fromtimestamp(101, timezone.utc),
        scheduler=scheduler,
        models=evaluation_models,
    )
    assert [row.assessment_id for row in repeated] == [result[0].assessment_id]
    assert len(session.exec(select(Assessment)).all()) == 1


def test_models_use_their_own_allowance_and_keep_existing_deadlines(
    *, session, engine, assessment_queue
):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)
    scheduler = SchedulerState(queue=assessment_queue)

    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=1_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
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

    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    originals = {
        row.model_id: row
        for row in evaluate_case(
            case_id="case",
            evaluation_id=uuid4(),
            engine=engine,
            now=lambda: datetime.fromtimestamp(100, timezone.utc),
            scheduler=scheduler,
            models=evaluation_models,
        )
    }

    assert originals["short"].next_due_at_us == 102_000_000
    assert originals["long"].next_due_at_us == 120_000_000
    for row in originals.values():
        assert row.status == "pending"
        explanation = Explanation.model_validate_json(row.explanation_json)
        assert explanation.rules[0].deadline_at.timestamp() * 1_000_000 == row.next_due_at_us
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    assert [
        row.model_dump()
        for row in evaluate_case(
            case_id="case",
            evaluation_id=uuid4(),
            engine=engine,
            now=lambda: datetime.fromtimestamp(101, timezone.utc),
            scheduler=scheduler,
            models=evaluation_models,
        )
    ] == [row.model_dump() for row in originals.values()]

    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    checked = {
        row.model_id: row
        for row in check_repairs(
            case_id="case",
            evaluation_id=uuid4(),
            engine=engine,
            now=lambda: datetime.fromtimestamp(102, timezone.utc),
            scheduler=scheduler,
            models=evaluation_models,
        )
    }
    assert checked["short"].status == "conformant"
    assert checked["short"].resolves_assessment_id == originals["short"].assessment_id
    assert checked["long"].model_dump() == originals["long"].model_dump()


def test_replay_requests_repair_after_enqueue_failure_without_repeating_assessment(
    *, session, engine, assessment_queue, monkeypatch
):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)
    scheduler = SchedulerState(queue=assessment_queue)
    received_at = datetime(2026, 9, 26, 9, 2, 3, 456_789, tzinfo=timezone.utc)
    with read_session(engine=engine) as catalog_session:
        model_catalog = list_models(session=catalog_session)

    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=1_500_000,
            received_at_us=0,
            transcript="stop that right now please",
            signal_level_min=-60.0,
            signal_level_avg=-16.0,
            signal_level_max=0.0,
        ),
    )
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
            models=model_catalog,
        )

    monkeypatch.setattr(assessment_queue, "put", put)
    results = evaluate_case(
        case_id="case",
        evaluation_id=evaluation_id,
        engine=engine,
        now=lambda: received_at,
        scheduler=scheduler,
        models=model_catalog,
    )
    with read_session(engine=engine) as session:
        assert len(session.exec(select(Assessment)).all()) == 1
    assert len(results) == 1
    assert results[0].evaluation_id == str(evaluation_id)
    assert assessment_queue.get(block=False)["kind"] == "check_repairs"


def test_shutdown_finishes_assessment_without_enqueuing_repair(
    *, session, engine, assessment_queue
):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)
    scheduler = SchedulerState(queue=assessment_queue)

    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=1_500_000,
            received_at_us=0,
            transcript="stop that right now please",
            signal_level_min=-60.0,
            signal_level_avg=-16.0,
            signal_level_max=0.0,
        ),
    )
    scheduler.stopped.set()
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    assert (
        evaluate_case(
            case_id="case",
            evaluation_id=uuid4(),
            engine=engine,
            now=lambda: datetime.fromtimestamp(100, timezone.utc),
            scheduler=scheduler,
            models=evaluation_models,
        )[0].status
        == "pending"
    )
    assert assessment_queue.empty()


def test_replayed_evaluation_preserves_its_original_results(*, session, engine, assessment_queue):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)
    scheduler = SchedulerState(queue=assessment_queue)

    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=1_500_000,
            received_at_us=0,
            transcript="stop that right now please",
            signal_level_min=-60.0,
            signal_level_avg=-16.0,
            signal_level_max=0.0,
        ),
    )
    evaluation_id = uuid4()
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    original = evaluate_case(
        case_id="case",
        evaluation_id=evaluation_id,
        engine=engine,
        now=lambda: datetime.fromtimestamp(100, timezone.utc),
        scheduler=scheduler,
        models=evaluation_models,
    )
    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=1_000_000,
            end_at_us=32_000_000,
            received_at_us=101_000_000,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )

    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    replayed = evaluate_case(
        case_id="case",
        evaluation_id=evaluation_id,
        engine=engine,
        now=lambda: datetime.fromtimestamp(102, timezone.utc),
        scheduler=scheduler,
        models=evaluation_models,
    )

    assert [row.model_dump() for row in replayed] == [row.model_dump() for row in original]
    assert replayed[0].through_sequence == 1
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    assert {
        row.model_id
        for row in evaluate_case(
            case_id="case",
            evaluation_id=uuid4(),
            engine=engine,
            now=lambda: datetime.fromtimestamp(102, timezone.utc),
            scheduler=scheduler,
            models=evaluation_models,
        )
    } == {
        "high_intensity_address",
        "extended_turn",
    }


def test_failed_assessment_rolls_back_all_models_before_requesting_repairs(
    *, session, engine, assessment_queue
):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)
    scheduler = SchedulerState(queue=assessment_queue)

    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=1_500_000,
            received_at_us=0,
            transcript="stop that right now please",
            signal_level_min=-60.0,
            signal_level_avg=-16.0,
            signal_level_max=0.0,
        ),
    )
    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=1_000_000,
            end_at_us=32_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    # Extended turn is stored first; fail the second model's write.
    with engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE TRIGGER fail_assessment BEFORE INSERT ON assessment
            WHEN NEW.model_id = 'high_intensity_address'
            BEGIN SELECT RAISE(ABORT, 'Assessment write failed'); END
        """)

    with pytest.raises(StorageUnavailable, match="The case could not be assessed"):
        with read_session(engine=engine) as catalog_session:
            evaluation_models = list_models(session=catalog_session)
        evaluate_case(
            case_id="case",
            evaluation_id=uuid4(),
            engine=engine,
            now=lambda: datetime.fromtimestamp(100, timezone.utc),
            scheduler=scheduler,
            models=evaluation_models,
        )

    with read_session(engine=engine) as session:
        assert session.exec(select(Assessment)).all() == []
    assert assessment_queue.empty()


def test_new_matches_share_the_case_evaluation_time(*, session, engine, assessment_queue):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)
    scheduler = SchedulerState(queue=assessment_queue)
    with read_session(engine=engine) as catalog_session:
        model_catalog = list_models(session=catalog_session)

    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=1_500_000,
            received_at_us=0,
            transcript="stop that right now please",
            signal_level_min=-60.0,
            signal_level_avg=-16.0,
            signal_level_max=0.0,
        ),
    )
    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=1_000_000,
            end_at_us=32_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    times = iter([100])

    results = evaluate_case(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        scheduler=scheduler,
        now=lambda: datetime.fromtimestamp(next(times), timezone.utc),
        models=model_catalog,
    )

    assert [(row.model_id, row.evaluated_at_us, row.next_due_at_us) for row in results] == [
        ("extended_turn", 100_000_000, 110_000_000),
        ("high_intensity_address", 100_000_000, 110_000_000),
    ]


def test_models_share_one_subject_lookup(
    *, session, engine, assessment_queue, subject_config_reads
):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)
    scheduler = SchedulerState(queue=assessment_queue)

    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=1_500_000,
            received_at_us=0,
            transcript="stop that right now please",
            signal_level_min=-60.0,
            signal_level_avg=-16.0,
            signal_level_max=0.0,
        ),
    )
    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=1_000_000,
            end_at_us=32_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )

    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    assert (
        len(
            evaluate_case(
                case_id="case",
                evaluation_id=uuid4(),
                engine=engine,
                now=lambda: datetime.fromtimestamp(100, timezone.utc),
                scheduler=scheduler,
                models=evaluation_models,
            )
        )
        == 2
    )
    assert len(subject_config_reads) == 1


def test_replay_preserves_pending_result_after_resolution(*, session, engine, assessment_queue):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)
    scheduler = SchedulerState(queue=assessment_queue)

    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=1_500_000,
            received_at_us=0,
            transcript="stop that right now please",
            signal_level_min=-60.0,
            signal_level_avg=-16.0,
            signal_level_max=0.0,
        ),
    )
    evaluation_id = uuid4()
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    original = evaluate_case(
        case_id="case",
        evaluation_id=evaluation_id,
        engine=engine,
        now=lambda: datetime.fromtimestamp(100, timezone.utc),
        scheduler=scheduler,
        models=evaluation_models,
    )[0]
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    final = check_repairs(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        now=lambda: datetime.fromtimestamp(110, timezone.utc),
        scheduler=scheduler,
        models=evaluation_models,
    )[0]
    assert final.resolves_assessment_id == original.assessment_id

    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    replayed = evaluate_case(
        case_id="case",
        evaluation_id=evaluation_id,
        engine=engine,
        now=lambda: datetime.fromtimestamp(111, timezone.utc),
        scheduler=scheduler,
        models=evaluation_models,
    )

    assert [row.model_dump() for row in replayed] == [original.model_dump()]


def test_model_added_after_the_catalog_was_loaded_is_not_assessed(
    *, session, engine, assessment_queue
):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)
    scheduler = SchedulerState(queue=assessment_queue)
    with read_session(engine=engine) as catalog_session:
        model_catalog = list_models(session=catalog_session)
    received_at = datetime(2026, 9, 26, 9, 2, 3, 456_789, tzinfo=timezone.utc)

    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=1_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    session.add(
        NormativeModelVersion(
            model_id="late",
            version="1",
            name="Late",
            type="undesired",
            repair_allowance_us=None,
            rules_json='[{"rule_id":"always","description":"Always matches","sql":"SELECT 1"}]',
            parameters_json="{}",
        )
    )
    session.commit()

    results = evaluate_case(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        now=lambda: received_at,
        scheduler=scheduler,
        models=model_catalog,
    )

    assert results == []
