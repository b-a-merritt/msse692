from datetime import datetime
from datetime import timezone
from itertools import count
from uuid import uuid4

import pytest
from sqlmodel import select

from normative_conformance import models
from normative_conformance.database import read_session
from normative_conformance.errors import StorageUnavailable
from normative_conformance.models.assessment import Assessment
from normative_conformance.services.assessment.check_repairs import check_repairs
from normative_conformance.services.assessment.evaluate_case import evaluate_case
from normative_conformance.services.model.list_models import list_models
from normative_conformance.services.scheduler.state import SchedulerState

from ...storage import persist


def test_repair_can_resolve_multiple_pending_models(*, session, engine, assessment_queue):
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
    pending = evaluate_case(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        now=lambda: datetime.fromtimestamp(100, timezone.utc),
        scheduler=scheduler,
        models=evaluation_models,
    )
    assert len(pending) == 2
    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=33_000_000,
            end_at_us=34_000_000,
            received_at_us=105_000_000,
            transcript="I am sorry",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    resolutions = [
        row
        for row in check_repairs(
            case_id="case",
            evaluation_id=uuid4(),
            engine=engine,
            now=lambda: datetime.fromtimestamp(105, timezone.utc),
            scheduler=scheduler,
            models=evaluation_models,
        )
        if row.resolves_assessment_id is not None
    ]
    assert {row.resolves_assessment_id for row in resolutions} == {
        row.assessment_id for row in pending
    }
    assert all(row.status == "non-conformant" for row in resolutions)


def test_repair_searches_and_resolutions_share_one_subject_lookup(
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
    evaluate_case(
        case_id="case",
        evaluation_id=uuid4(),
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
            start_at_us=33_000_000,
            end_at_us=34_000_000,
            received_at_us=105_000_000,
            transcript="I apologize",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    subject_config_reads.clear()

    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    results = check_repairs(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        now=lambda: datetime.fromtimestamp(105, timezone.utc),
        scheduler=scheduler,
        models=evaluation_models,
    )

    assert len(results) == 3
    assert len(subject_config_reads) == 1


def test_late_repair_resets_future_detection_without_retracting_positive(
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
    evaluate_case(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        now=lambda: datetime.fromtimestamp(100, timezone.utc),
        scheduler=scheduler,
        models=evaluation_models,
    )
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
    before = final.model_dump()
    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=1_000_000,
            end_at_us=2_000_000,
            received_at_us=111_000_000,
            transcript="I apologize",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    check_repairs(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        now=lambda: datetime.fromtimestamp(111, timezone.utc),
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
            start_at_us=3_000_000,
            end_at_us=4_500_000,
            received_at_us=112_000_000,
            transcript="stop that right now please",
            signal_level_min=-60.0,
            signal_level_avg=-16.0,
            signal_level_max=0.0,
        ),
    )
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    new = evaluate_case(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        now=lambda: datetime.fromtimestamp(112, timezone.utc),
        scheduler=scheduler,
        models=evaluation_models,
    )[0]
    assert new.status == "pending"
    assert new.next_due_at_us == 122_000_000
    assert session.get(Assessment, final.assessment_id).model_dump() == before


def test_repair_resets_incomplete_interruption_pattern(*, session, engine, assessment_queue):
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
            speaker_id="other",
            start_at_us=0,
            end_at_us=20_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
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
            end_at_us=2_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
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
            start_at_us=3_000_000,
            end_at_us=4_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
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
            start_at_us=5_000_000,
            end_at_us=6_000_000,
            received_at_us=0,
            transcript="I apologize",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
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
            start_at_us=7_000_000,
            end_at_us=8_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    # Detection submits a candidate; the separate repair check removes the old evidence.
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
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    check_repairs(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        now=lambda: datetime.fromtimestamp(100, timezone.utc),
        scheduler=scheduler,
        models=evaluation_models,
    )
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    assert (
        evaluate_case(
            case_id="case",
            evaluation_id=uuid4(),
            engine=engine,
            now=lambda: datetime.fromtimestamp(101, timezone.utc),
            scheduler=scheduler,
            models=evaluation_models,
        )
        == []
    )


def test_repeated_checks_append_only_one_resolution(*, session, engine, assessment_queue):
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
            end_at_us=31_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
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
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    first = check_repairs(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        now=lambda: datetime.fromtimestamp(110, timezone.utc),
        scheduler=scheduler,
        models=evaluation_models,
    )
    assert len(first) == 1
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    assert (
        check_repairs(
            case_id="case",
            evaluation_id=uuid4(),
            engine=engine,
            now=lambda: datetime.fromtimestamp(111, timezone.utc),
            scheduler=scheduler,
            models=evaluation_models,
        )
        == []
    )
    assert len(session.exec(select(Assessment)).all()) == 2


@pytest.mark.parametrize("stopping", [False, True])
def test_repair_requests_assessment_after_commit_unless_stopping(
    *, session, engine, assessment_queue, monkeypatch, stopping
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
    original = evaluate_case(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        now=lambda: datetime.fromtimestamp(100, timezone.utc),
        scheduler=scheduler,
        models=evaluation_models,
    )[0]
    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=1_000_000,
            end_at_us=2_000_000,
            received_at_us=105_000_000,
            transcript="I apologize",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    put = assessment_queue.put
    requested = []

    def enqueue(*, item):
        with read_session(engine=engine) as session:
            resolution = session.exec(
                select(Assessment).where(
                    Assessment.resolves_assessment_id == original.assessment_id
                )
            ).one()
            assert resolution.status == "non-conformant"
        requested.append(item["kind"])
        return put(item=item)

    monkeypatch.setattr(assessment_queue, "put", enqueue)
    if stopping:
        scheduler.stopped.set()
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    results = check_repairs(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        now=lambda: datetime.fromtimestamp(105, timezone.utc),
        scheduler=scheduler,
        models=evaluation_models,
    )

    assert any(row.resolves_assessment_id == original.assessment_id for row in results)
    assert requested == ([] if stopping else ["assess_case"])


@pytest.mark.parametrize("at", [105, 110])
def test_check_without_repair_does_not_request_assessment(*, session, engine, assessment_queue, at):
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
    evaluate_case(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        now=lambda: datetime.fromtimestamp(100, timezone.utc),
        scheduler=scheduler,
        models=evaluation_models,
    )

    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    results = check_repairs(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        now=lambda: datetime.fromtimestamp(at, timezone.utc),
        scheduler=scheduler,
        models=evaluation_models,
    )

    assert results[0].status == ("pending" if at < 110 else "conformant")
    assert scheduler.queued_cases == set()


def test_failed_resolution_rolls_back_repair_before_requesting_assessment(
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
    original = evaluate_case(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        now=lambda: datetime.fromtimestamp(100, timezone.utc),
        scheduler=scheduler,
        models=evaluation_models,
    )[0]
    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=1_000_000,
            end_at_us=2_000_000,
            received_at_us=105_000_000,
            transcript="I apologize",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    # The apology is stored first; a failed resolution must roll it back too.
    with engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE TRIGGER fail_resolution BEFORE INSERT ON assessment
            WHEN NEW.resolves_assessment_id IS NOT NULL
            BEGIN SELECT RAISE(ABORT, 'Resolution write failed'); END
        """)

    with pytest.raises(StorageUnavailable, match="Repairs could not be checked"):
        with read_session(engine=engine) as catalog_session:
            evaluation_models = list_models(session=catalog_session)
        check_repairs(
            case_id="case",
            evaluation_id=uuid4(),
            engine=engine,
            now=lambda: datetime.fromtimestamp(105, timezone.utc),
            scheduler=scheduler,
            models=evaluation_models,
        )

    with read_session(engine=engine) as session:
        rows = session.exec(select(Assessment)).all()
        assert [row.model_dump() for row in rows] == [original.model_dump()]
    assert scheduler.queued_cases == set()
