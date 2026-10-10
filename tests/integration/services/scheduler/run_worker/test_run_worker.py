"""The worker acknowledges results, preserves follow-up requests, and groups interventions."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from datetime import timezone
from itertools import count
from threading import Event
from threading import Thread
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlmodel import select

from normative_conformance import models
from normative_conformance import models as db_models
from normative_conformance.database import read_session
from normative_conformance.errors import EnqueueFailed
from normative_conformance.services import assessment
from normative_conformance.services import intervention
from normative_conformance.services.model.list_models import list_models
from normative_conformance.services.scheduler.request_assessment import request_assessment
from normative_conformance.services.scheduler.request_repair_check import request_repair_check
from normative_conformance.services.scheduler.run_worker import run_worker
from normative_conformance.services.scheduler.state import SchedulerState
from normative_conformance.timestamps import from_microseconds

from ....storage import persist
from ....storage import persist_in_database

WINDOW_US = 2_000_000


def test_initial_deadline_load_failure_stops_worker(*, assessment_queue, empty_engine):
    scheduler = SchedulerState(queue=assessment_queue)
    received_at = datetime(2026, 9, 26, 9, 2, 3, 456_789, tzinfo=timezone.utc)

    request_assessment(case_id="case", scheduler=scheduler)

    run_worker(
        scheduler=scheduler,
        engine=empty_engine,
        now=lambda: received_at,
        intervention_window_us=WINDOW_US,
        models=[],
    )

    assert scheduler.stopped.is_set()
    assert assessment_queue.qsize() == 1
    assert assessment_queue.unack_count() == 0


def test_due_repair_enqueue_failure_stops_worker(*, engine, assessment_queue, session, monkeypatch):
    scheduler = SchedulerState(queue=assessment_queue)
    session.add(
        db_models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0)
    )
    session.add(db_models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)
    with read_session(engine=engine) as catalog_session:
        model_catalog = list_models(session=catalog_session)

    persist(
        session=session,
        record=db_models.Observation(
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
    assessments = assessment.evaluate_case(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        scheduler=scheduler,
        now=lambda: from_microseconds(value=100_000_000),
        models=model_catalog,
    )
    due_at_us = min(row.next_due_at_us for row in assessments if row.next_due_at_us is not None)
    scheduler.stopped.clear()
    monkeypatch.setattr(
        assessment_queue, "put", Mock(side_effect=sqlite3.OperationalError("Queue failed"))
    )

    run_worker(
        scheduler=scheduler,
        engine=engine,
        now=lambda: from_microseconds(value=due_at_us),
        intervention_window_us=WINDOW_US,
        models=model_catalog,
    )

    assert scheduler.stopped.is_set()
    assert assessment_queue.qsize() == 0


def test_shutdown_discards_open_windows_without_recovering_them_on_restart(
    *, engine, session, assessment_queue, monkeypatch
):
    scheduler = SchedulerState(queue=assessment_queue)
    session.add(
        db_models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0)
    )
    session.add(db_models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    persist(
        session=session,
        record=db_models.Observation(
            case_id="case",
            observation_id="1",
            sequence=1,
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
        model_catalog = list_models(session=catalog_session)

    def evaluate_case(*, case_id, evaluation_id, engine, now, scheduler, models):
        result = persist_in_database(
            engine=engine,
            record=db_models.Assessment(
                evaluation_id=str(evaluation_id),
                case_id="case",
                model_id="harm_phrase",
                model_version="1",
                evaluated_at_us=100_000_000,
                through_sequence=1,
                status="conformant",
                explanation_json="{}",
            ),
        )
        scheduler.stopped.set()
        return [result]

    monkeypatch.setattr(assessment, "evaluate_case", evaluate_case)
    request_assessment(case_id="case", scheduler=scheduler)
    run_worker(
        scheduler=scheduler,
        engine=engine,
        now=lambda: from_microseconds(value=100_000_000),
        intervention_window_us=WINDOW_US,
        models=model_catalog,
    )
    assert assessment_queue.acked_count() == 1

    original_get = assessment_queue.get

    def stop_when_empty(*, timeout):
        scheduler.stopped.set()
        return original_get(timeout=timeout)

    monkeypatch.setattr(assessment_queue, "get", stop_when_empty)
    scheduler.stopped.clear()
    run_worker(
        scheduler=scheduler,
        engine=engine,
        now=lambda: from_microseconds(value=200_000_000),
        intervention_window_us=WINDOW_US,
        models=model_catalog,
    )

    assert scheduler.stopped.is_set()
    assert intervention.list_intervention_records(session=session) == []


def test_arrivals_during_evaluation_share_one_follow_up(*, assessment_queue, engine, monkeypatch):
    scheduler = SchedulerState(queue=assessment_queue)
    received_at = datetime(2026, 9, 26, 9, 2, 3, 456_789, tzinfo=timezone.utc)
    with read_session(engine=engine) as catalog_session:
        model_catalog = list_models(session=catalog_session)

    entered = Event()
    release = Event()
    evaluations = []

    def evaluate_case(*, case_id, evaluation_id, engine, now, scheduler, models):
        evaluations.append(evaluation_id)
        if len(evaluations) == 1:
            entered.set()
            assert release.wait(timeout=5)
        else:
            scheduler.stopped.set()
        return []

    monkeypatch.setattr(assessment, "evaluate_case", evaluate_case)
    request_assessment(case_id="case", scheduler=scheduler)
    worker = Thread(
        target=run_worker,
        kwargs={
            "scheduler": scheduler,
            "engine": engine,
            "now": lambda: received_at,
            "intervention_window_us": WINDOW_US,
            "models": model_catalog,
        },
    )
    worker.start()
    try:
        assert entered.wait(timeout=5)
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(request_assessment, case_id="case", scheduler=scheduler)
                for _ in range(8)
            ]
            for future in futures:
                future.result(timeout=5)
        assert assessment_queue.qsize() == 1
        release.set()
        worker.join(timeout=5)
        assert not worker.is_alive()
    finally:
        scheduler.stopped.set()
        release.set()
        worker.join(timeout=5)
    assert len(set(evaluations)) == 2
    assert assessment_queue.acked_count() == 2
    assert assessment_queue.empty()


def test_failed_evaluation_does_not_retry_or_stop_other_cases(
    *, assessment_queue, engine, monkeypatch
):
    scheduler = SchedulerState(queue=assessment_queue)
    received_at = datetime(2026, 9, 26, 9, 2, 3, 456_789, tzinfo=timezone.utc)
    with read_session(engine=engine) as catalog_session:
        model_catalog = list_models(session=catalog_session)

    request_assessment(case_id="failing", scheduler=scheduler)
    request_assessment(case_id="next", scheduler=scheduler)
    evaluated = []

    def evaluate_case(*, case_id, evaluation_id, engine, now, scheduler, models):
        evaluated.append(case_id)
        if case_id == "failing":
            raise RuntimeError("Evaluation failed")
        scheduler.stopped.set()
        return []

    monkeypatch.setattr(assessment, "evaluate_case", evaluate_case)
    run_worker(
        scheduler=scheduler,
        engine=engine,
        now=lambda: received_at,
        intervention_window_us=WINDOW_US,
        models=model_catalog,
    )
    assert evaluated == ["failing", "next"]
    assert assessment_queue.ack_failed_count() == 1
    assert assessment_queue.acked_count() == 1
    assert assessment_queue.empty()


def test_unknown_task_is_failed_without_stopping_other_cases(
    *, assessment_queue, engine, monkeypatch
):
    scheduler = SchedulerState(queue=assessment_queue)
    received_at = datetime(2026, 9, 26, 9, 2, 3, 456_789, tzinfo=timezone.utc)
    with read_session(engine=engine) as catalog_session:
        model_catalog = list_models(session=catalog_session)

    assessment_queue.put(
        item={"kind": "unknown", "case_id": "invalid", "evaluation_id": str(uuid4())}
    )
    request_assessment(case_id="next", scheduler=scheduler)
    evaluated = []

    def evaluate_case(*, case_id, evaluation_id, engine, now, scheduler, models):
        evaluated.append(case_id)
        scheduler.stopped.set()
        return []

    monkeypatch.setattr(assessment, "evaluate_case", evaluate_case)
    run_worker(
        scheduler=scheduler,
        engine=engine,
        now=lambda: received_at,
        intervention_window_us=WINDOW_US,
        models=model_catalog,
    )

    assert evaluated == ["next"]
    assert assessment_queue.ack_failed_count() == 1
    assert assessment_queue.acked_count() == 1


@pytest.mark.parametrize("restart", [False, True])
def test_worker_checks_deadline_without_more_observations(
    *, engine, assessment_queue, session, monkeypatch, restart
):
    scheduler = SchedulerState(queue=assessment_queue)
    session.add(
        db_models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0)
    )
    session.add(db_models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)
    with read_session(engine=engine) as catalog_session:
        model_catalog = list_models(session=catalog_session)

    persist(
        session=session,
        record=db_models.Observation(
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
    deadline = Event()
    checked_early = Event()
    completed = Event()
    resolutions = []
    original_check = assessment.check_repairs

    def clock():
        return datetime.fromtimestamp(110 if deadline.is_set() else 100, timezone.utc)

    if restart:
        # Simulate an assessment finishing during shutdown, leaving only its stored deadline.
        scheduler.stopped.set()
        assessment.evaluate_case(
            case_id="case",
            evaluation_id=uuid4(),
            engine=engine,
            now=clock,
            scheduler=scheduler,
            models=model_catalog,
        )
        scheduler.stopped.clear()
        assert assessment_queue.empty()
        deadline.set()
    else:
        request_assessment(case_id="case", scheduler=scheduler)

    def check_repairs(*, case_id, evaluation_id, engine, now, scheduler, models):
        results = original_check(
            case_id=case_id,
            evaluation_id=evaluation_id,
            engine=engine,
            now=now,
            scheduler=scheduler,
            models=models,
        )
        checked_early.set()
        resolutions.extend(row for row in results if row.resolves_assessment_id is not None)
        if resolutions:
            scheduler.stopped.set()
            completed.set()
        return results

    monkeypatch.setattr(assessment, "check_repairs", check_repairs)
    worker = Thread(
        target=run_worker,
        kwargs={
            "scheduler": scheduler,
            "engine": engine,
            "now": clock,
            "intervention_window_us": WINDOW_US,
            "models": model_catalog,
        },
    )
    worker.start()
    try:
        if not restart:
            assert checked_early.wait(timeout=5)
            deadline.set()
        assert completed.wait(timeout=5)
    finally:
        scheduler.stopped.set()
        worker.join(timeout=5)
    assert not worker.is_alive()
    assert len(resolutions) == 1
    assert resolutions[0].status == "conformant"
    assert assessment_queue.acked_count() == (1 if restart else 3)


def test_repaired_match_requests_another_assessment(
    *, engine, assessment_queue, session, monkeypatch
):
    scheduler = SchedulerState(queue=assessment_queue)
    session.add(
        db_models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0)
    )
    session.add(db_models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)
    with read_session(engine=engine) as catalog_session:
        model_catalog = list_models(session=catalog_session)

    persist(
        session=session,
        record=db_models.Observation(
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

    def clock():
        return datetime.fromtimestamp(100, timezone.utc)

    assessment.evaluate_case(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        now=clock,
        scheduler=scheduler,
        models=model_catalog,
    )
    persist(
        session=session,
        record=db_models.Observation(
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
    request_repair_check(case_id="case", scheduler=scheduler)
    assessed = []

    def evaluate_case(*, case_id, evaluation_id, engine, now, scheduler, models):
        assessed.append(case_id)
        scheduler.stopped.set()
        return []

    monkeypatch.setattr(assessment, "evaluate_case", evaluate_case)
    run_worker(
        scheduler=scheduler,
        engine=engine,
        now=lambda: datetime.fromtimestamp(105, timezone.utc),
        intervention_window_us=WINDOW_US,
        models=model_catalog,
    )
    assert assessed == ["case"]


@pytest.mark.parametrize("operation", ["get", "ack", "ack_failed"])
def test_queue_failure_stops_worker_and_rejects_new_requests(
    *, assessment_queue, engine, monkeypatch, operation
):
    scheduler = SchedulerState(queue=assessment_queue)
    received_at = datetime(2026, 9, 26, 9, 2, 3, 456_789, tzinfo=timezone.utc)
    with read_session(engine=engine) as catalog_session:
        model_catalog = list_models(session=catalog_session)

    request_assessment(case_id="case", scheduler=scheduler)
    request_assessment(case_id="waiting", scheduler=scheduler)
    monkeypatch.setattr(
        assessment,
        "evaluate_case",
        Mock(side_effect=RuntimeError("Evaluation failed"))
        if operation == "ack_failed"
        else Mock(return_value=[]),
    )
    monkeypatch.setattr(
        assessment_queue, operation, Mock(side_effect=sqlite3.OperationalError("Queue failed"))
    )
    run_worker(
        scheduler=scheduler,
        engine=engine,
        now=lambda: received_at,
        intervention_window_us=WINDOW_US,
        models=model_catalog,
    )
    assert scheduler.stopped.is_set()
    assert assessment_queue.acked_count() == 0
    assert assessment_queue.ack_failed_count() == 0
    assert assessment_queue.qsize() == (2 if operation == "get" else 1)
    assert assessment_queue.unack_count() == (0 if operation == "get" else 1)
    with pytest.raises(EnqueueFailed, match="The assessment worker is not running"):
        request_assessment(case_id="new", scheduler=scheduler)


@pytest.mark.parametrize(
    ("gap", "groups"),
    [
        pytest.param(1.0, [["repeated_interruption", "high_intensity_address"]], id="close"),
        pytest.param(3.0, [["repeated_interruption"], ["high_intensity_address"]], id="apart"),
    ],
)
def test_confirmations_within_the_window_share_one_intervention(
    *, assessment_queue, session, engine, monkeypatch, gap, groups
):
    scheduler = SchedulerState(queue=assessment_queue)
    session.add(
        db_models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0)
    )
    session.add(db_models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    persist(
        session=session,
        record=db_models.Observation(
            case_id="case",
            observation_id="1",
            sequence=1,
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
        model_catalog = list_models(session=catalog_session)

    _, done = _record_decisions(monkeypatch=monkeypatch, count=len(groups))
    clock = {"at": 100.0}
    remaining = ["repeated_interruption", "high_intensity_address"]

    def evaluate_case(*, case_id, evaluation_id, engine, now, scheduler, models):
        row = persist_in_database(
            engine=engine,
            record=db_models.Assessment(
                evaluation_id=str(evaluation_id),
                case_id="case",
                model_id=remaining.pop(0),
                model_version="1",
                evaluated_at_us=round((clock["at"]) * 1_000_000),
                through_sequence=1,
                status="conformant",
                explanation_json="{}",
            ),
        )
        if remaining:
            clock["at"] += gap
            request_assessment(case_id=case_id, scheduler=scheduler)
        else:
            clock["at"] += WINDOW_US / 1_000_000
        return [row]

    monkeypatch.setattr(assessment, "evaluate_case", evaluate_case)
    request_assessment(case_id="case", scheduler=scheduler)
    _run_until(
        scheduler=scheduler, engine=engine, model_catalog=model_catalog, clock=clock, done=done
    )

    model_ids = {row.assessment_id: row.model_id for row in session.exec(select(models.Assessment))}
    records = intervention.list_intervention_records(session=session)
    assert [[model_ids[id] for id in record.assessment_ids] for record in records] == groups


@pytest.mark.parametrize(
    "early_result",
    [
        "repair",
        "reused",
        "replayed",
    ],
)
def test_ineligible_results_do_not_split_later_confirmations(
    *, assessment_queue, session, engine, monkeypatch, early_result
):
    scheduler = SchedulerState(queue=assessment_queue)
    session.add(
        db_models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0)
    )
    session.add(db_models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    persist(
        session=session,
        record=db_models.Observation(
            case_id="case",
            observation_id="1",
            sequence=1,
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
        model_catalog = list_models(session=catalog_session)

    decisions, done = _record_decisions(monkeypatch=monkeypatch, count=1)
    clock = {"at": 100.0}
    remaining = ["high_intensity_address", "repeated_interruption"]

    def handle(*, case_id, evaluation_id, engine, now, scheduler, models):
        if clock["at"] == 100:
            row = persist_in_database(
                engine=engine,
                record=db_models.Assessment(
                    evaluation_id=str(uuid4() if early_result == "reused" else evaluation_id),
                    case_id="case",
                    model_id="apology" if early_result == "repair" else "harm_phrase",
                    model_version="1",
                    evaluated_at_us=((50 if early_result == "replayed" else 100) * 1_000_000),
                    through_sequence=1,
                    status="conformant",
                    explanation_json="{}",
                ),
            )
            clock["at"] = 101.9
        else:
            row = persist_in_database(
                engine=engine,
                record=db_models.Assessment(
                    evaluation_id=str(evaluation_id),
                    case_id="case",
                    model_id=remaining.pop(0),
                    model_version="1",
                    evaluated_at_us=round((clock["at"]) * 1_000_000),
                    through_sequence=1,
                    status="conformant",
                    explanation_json="{}",
                ),
            )
            clock["at"] = 102.1 if remaining else 104.0
        if remaining:
            request_assessment(case_id=case_id, scheduler=scheduler)
        return [row]

    monkeypatch.setattr(assessment, "evaluate_case", handle)
    monkeypatch.setattr(assessment, "check_repairs", handle)
    request = request_repair_check if early_result == "repair" else request_assessment
    request(case_id="case", scheduler=scheduler)
    _run_until(
        scheduler=scheduler, engine=engine, model_catalog=model_catalog, clock=clock, done=done
    )

    assert decisions == [101_900_000]
    model_ids = {row.assessment_id: row.model_id for row in session.exec(select(models.Assessment))}
    records = intervention.list_intervention_records(session=session)
    assert [[model_ids[id] for id in record.assessment_ids] for record in records] == [
        ["high_intensity_address", "repeated_interruption"]
    ]


@pytest.mark.parametrize("first", ["immediate", "repair-deadline"])
def test_immediate_and_repair_deadline_confirmations_share_one_intervention(
    *, engine, assessment_queue, session, monkeypatch, first
):
    scheduler = SchedulerState(queue=assessment_queue)
    session.add(
        db_models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0)
    )
    session.add(db_models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)
    with read_session(engine=engine) as catalog_session:
        model_catalog = list_models(session=catalog_session)

    persist(
        session=session,
        record=db_models.Observation(
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
    assessment.evaluate_case(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        scheduler=scheduler,
        now=lambda: datetime.fromtimestamp(100, timezone.utc),
        models=model_catalog,
    )
    persist(
        session=session,
        record=db_models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=1_000_000,
            end_at_us=2_000_000,
            received_at_us=0,
            transcript="I hope you die",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    request_assessment(case_id="case", scheduler=scheduler)
    decisions, done = _record_decisions(monkeypatch=monkeypatch, count=1)
    clock = {"at": 109.0 if first == "immediate" else 110.0}
    original_evaluate = assessment.evaluate_case
    original_check = assessment.check_repairs

    def evaluate_case(**kwargs):
        results = original_evaluate(**kwargs)
        clock["at"] = 110 if first == "immediate" else 112
        return results

    def check_repairs(**kwargs):
        results = original_check(**kwargs)
        if any(row.status == "conformant" and row.resolves_assessment_id for row in results):
            clock["at"] = 112 if first == "immediate" else 111
        return results

    monkeypatch.setattr(assessment, "evaluate_case", evaluate_case)
    monkeypatch.setattr(assessment, "check_repairs", check_repairs)
    _run_until(
        scheduler=scheduler, engine=engine, model_catalog=model_catalog, clock=clock, done=done
    )

    assert decisions == [109_000_000 if first == "immediate" else 110_000_000]
    records = intervention.list_intervention_records(session=session)
    assert len(records) == 1
    sources = [session.get(models.Assessment, id) for id in records[0].assessment_ids]
    assert {row.model_id for row in sources} == {"harm_phrase", "high_intensity_address"}
    assert sum(row.resolves_assessment_id is not None for row in sources) == 1


def test_slow_evaluation_keeps_later_confirmations_in_the_open_window(
    *, assessment_queue, session, engine, monkeypatch
):
    scheduler = SchedulerState(queue=assessment_queue)
    session.add(
        db_models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0)
    )
    session.add(db_models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    persist(
        session=session,
        record=db_models.Observation(
            case_id="case",
            observation_id="1",
            sequence=1,
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
        model_catalog = list_models(session=catalog_session)

    decisions, done = _record_decisions(monkeypatch=monkeypatch, count=1)
    clock = {"at": 100.0}
    remaining = ["high_intensity_address", "repeated_interruption"]

    def evaluate_case(*, case_id, evaluation_id, engine, now, scheduler, models):
        if len(remaining) == 1:
            clock["at"] = 103.5
        row = persist_in_database(
            engine=engine,
            record=db_models.Assessment(
                evaluation_id=str(evaluation_id),
                case_id="case",
                model_id=remaining.pop(0),
                model_version="1",
                evaluated_at_us=round((clock["at"]) * 1_000_000),
                through_sequence=1,
                status="conformant",
                explanation_json="{}",
            ),
        )
        if remaining:
            clock["at"] = 101.5
            request_assessment(case_id=case_id, scheduler=scheduler)
        return [row]

    monkeypatch.setattr(assessment, "evaluate_case", evaluate_case)
    request_assessment(case_id="case", scheduler=scheduler)
    _run_until(
        scheduler=scheduler, engine=engine, model_catalog=model_catalog, clock=clock, done=done
    )

    assert decisions == [100_000_000]
    records = intervention.list_intervention_records(session=session)
    assert len(records) == 1
    assert len(records[0].assessment_ids) == 2


def test_confirmed_match_becomes_one_intervention(
    *, assessment_queue, session, engine, monkeypatch
):
    scheduler = SchedulerState(queue=assessment_queue)
    session.add(
        db_models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0)
    )
    session.add(db_models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)
    with read_session(engine=engine) as catalog_session:
        model_catalog = list_models(session=catalog_session)

    _, done = _record_decisions(monkeypatch=monkeypatch, count=1)
    persist(
        session=session,
        record=db_models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=1_000_000,
            received_at_us=0,
            transcript="I hope you die",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    clock = {"at": 100.0}
    original = assessment.evaluate_case

    def evaluate_case(**kwargs):
        results = original(**kwargs)
        clock["at"] += WINDOW_US / 1_000_000
        return results

    monkeypatch.setattr(assessment, "evaluate_case", evaluate_case)
    request_assessment(case_id="case", scheduler=scheduler)
    _run_until(
        scheduler=scheduler, engine=engine, model_catalog=model_catalog, clock=clock, done=done
    )

    records = intervention.list_intervention_records(session=session)
    assert [record.message for record in records] == [
        "You said something that could be heard as a threat. Take a moment before you continue."
    ]


def test_intervention_failure_does_not_stop_work(*, assessment_queue, session, engine, monkeypatch):
    scheduler = SchedulerState(queue=assessment_queue)
    session.add(
        db_models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0)
    )
    session.add(db_models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    persist(
        session=session,
        record=db_models.Observation(
            case_id="case",
            observation_id="1",
            sequence=1,
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
        model_catalog = list_models(session=catalog_session)

    clock = {"at": 100.0}
    evaluated = []
    done = Event()

    def evaluate_case(*, case_id, evaluation_id, engine, now, scheduler, models):
        evaluated.append(case_id)
        if len(evaluated) > 1:
            done.set()
            return []
        row = persist_in_database(
            engine=engine,
            record=db_models.Assessment(
                evaluation_id=str(evaluation_id),
                case_id="case",
                model_id="harm_phrase",
                model_version="1",
                evaluated_at_us=round((clock["at"]) * 1_000_000),
                through_sequence=1,
                status="conformant",
                explanation_json="{}",
            ),
        )
        clock["at"] += WINDOW_US / 1_000_000
        request_assessment(case_id=case_id, scheduler=scheduler)
        return [row]

    failing = Mock(side_effect=RuntimeError("Intervention failed"))
    monkeypatch.setattr(assessment, "evaluate_case", evaluate_case)
    monkeypatch.setattr(intervention, "create_intervention", failing)
    request_assessment(case_id="case", scheduler=scheduler)
    _run_until(
        scheduler=scheduler, engine=engine, model_catalog=model_catalog, clock=clock, done=done
    )

    assert failing.call_count == 1
    assert evaluated == ["case", "case"]
    assert assessment_queue.acked_count() == 2


def _run_until(*, scheduler, engine, model_catalog, clock, done):
    worker = Thread(
        target=run_worker,
        kwargs={
            "scheduler": scheduler,
            "engine": engine,
            "now": lambda: datetime.fromtimestamp(clock["at"], timezone.utc),
            "intervention_window_us": 2_000_000,
            "models": model_catalog,
        },
    )
    worker.start()
    try:
        assert done.wait(timeout=5)
    finally:
        scheduler.stopped.set()
        worker.join(timeout=5)
    assert not worker.is_alive()


def _record_decisions(*, monkeypatch, count):
    decisions = []
    done = Event()
    original = intervention.create_intervention

    def create_intervention(**kwargs):
        original(**kwargs)
        decisions.append(kwargs["since_us"])
        if len(decisions) == count:
            done.set()

    monkeypatch.setattr(intervention, "create_intervention", create_intervention)
    return (decisions, done)
