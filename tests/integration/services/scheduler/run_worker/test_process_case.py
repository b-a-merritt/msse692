import json
from datetime import datetime
from datetime import timezone

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select

from normative_conformance.database import read_session
from normative_conformance.models.assessment import Assessment
from normative_conformance.models.case import CaseLog
from normative_conformance.models.normative_model import NormativeModelVersion
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.case import TargetSelection
from normative_conformance.services.case.selection import select_target
from normative_conformance.services.model.list_models import list_models
from normative_conformance.services.scheduler.run_worker.pending_cases import pending_cases
from normative_conformance.services.scheduler.run_worker.process_case import process_case


@pytest.mark.parametrize(
    "transcript,fail", [("hello", False), ("trigger", False), ("trigger", True)]
)
def test_results_and_cursor_commit_or_roll_back_together(engine, session, transcript, fail):
    session.add(CaseLog(case_id="case", created_at_us=0, target_speaker_id="A", target_revision=1))
    session.add(
        NormativeModelVersion(
            model_id="test",
            version="1",
            name="Test",
            type="undesired",
            parameters_json="{}",
            rules_json=json.dumps(
                [
                    {
                        "rule_id": "word",
                        "description": "",
                        "sql": "SELECT 1 FROM observation WHERE case_id = :case_id AND "
                        "speaker_id = :subject_speaker_id AND sequence <= :through_sequence "
                        "AND transcript = 'trigger'",
                    }
                ]
            ),
        )
    )
    session.flush()
    session.add(
        Observation(
            case_id="case",
            observation_id="one",
            sequence=1,
            received_at_us=0,
            updated_at_us=0,
            start_at_us=0,
            end_at_us=1,
            speaker_id="A",
            transcript=transcript,
            signal_level_min=-40,
            signal_level_avg=-30,
            signal_level_max=-20,
        )
    )
    session.commit()
    models = [m for m in list_models(session=session) if m.model_id == "test"]
    session.rollback()
    if fail:
        with engine.begin() as connection:
            connection.exec_driver_sql("""CREATE TRIGGER reject_progress BEFORE UPDATE ON case_log
                BEGIN SELECT RAISE(ABORT, 'failed progress'); END""")

    def now():
        return datetime(1970, 1, 1, microsecond=100, tzinfo=timezone.utc)

    if fail:
        with pytest.raises(SQLAlchemyError):
            process_case(case_id="case", engine=engine, now=now, models=models)
    else:
        assert process_case(case_id="case", engine=engine, now=now, models=models) == (
            100 if transcript == "trigger" else None
        )
    with read_session(engine=engine) as check:
        case = check.get(CaseLog, "case")
        assert (case.last_handled_sequence, case.last_handled_target_revision) == (
            (0, 0) if fail else (1, 1)
        )
        rows = check.exec(select(Assessment)).all()
        assert len(rows) == (1 if transcript == "trigger" and not fail else 0)
    engine.dispose()
    assert pending_cases(engine=engine, now_us=0) == (["case"] if fail else [])
    if fail:
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP TRIGGER reject_progress")
        process_case(case_id="case", engine=engine, now=now, models=models)
        assert pending_cases(engine=engine, now_us=0) == []


def test_unresolved_input_is_processed_after_target_selection_and_on_target_change(engine, session):
    session.add(CaseLog(case_id="case", created_at_us=0))
    session.flush()
    session.add(
        Observation(
            case_id="case",
            observation_id="one",
            sequence=1,
            received_at_us=0,
            updated_at_us=0,
            start_at_us=0,
            end_at_us=1,
            speaker_id="A",
            transcript="hello",
            signal_level_min=-40,
            signal_level_avg=-30,
            signal_level_max=-20,
        )
    )
    session.commit()

    def now():
        return datetime(1970, 1, 1, tzinfo=timezone.utc)

    assert pending_cases(engine=engine, now_us=0) == []
    assert process_case(case_id="case", engine=engine, now=now, models=[]) is None
    for label, revision in [("A", 1), ("B", 2)]:
        select_target(
            case_id="case",
            selection=TargetSelection(target_speaker_id=label),
            session=session,
            now=now,
        )
        assert pending_cases(engine=engine, now_us=0) == ["case"]
        process_case(case_id="case", engine=engine, now=now, models=[])
        session.expire_all()
        case = session.get(CaseLog, "case")
        assert case.last_handled_sequence == 1
        assert case.last_handled_target_revision == revision
        session.rollback()
        assert pending_cases(engine=engine, now_us=0) == []


def test_arrival_during_evaluation_remains_ready_after_commit(engine, session, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from importlib import import_module
    from threading import Event

    from normative_conformance.database import write_session
    from normative_conformance.schemas.observation import ObservationInput
    from normative_conformance.services.observation.ingest import ingest

    module = import_module("normative_conformance.services.scheduler.run_worker.process_case")

    def now():
        return datetime(1970, 1, 1, microsecond=100, tzinfo=timezone.utc)

    session.add(CaseLog(case_id="case", created_at_us=0, target_speaker_id="A"))
    session.commit()
    first = ObservationInput(
        case_id="case",
        observation_id="one",
        speaker_id="A",
        start_at="1970-01-01T00:00:00Z",
        end_at="1970-01-01T00:00:01Z",
        transcript="first",
        signal_level_min=-40,
        signal_level_avg=-30,
        signal_level_max=-20,
    )
    second = first.model_copy(update={"observation_id": "two", "transcript": "second"})
    ingest(input=first, session=session, now=now)
    evaluating = Event()
    release = Event()
    arriving = Event()
    original = module.evaluate_case

    def evaluate(**kwargs):
        evaluating.set()
        assert release.wait(5)
        return original(**kwargs)

    def arrive():
        arriving.set()
        with write_session(engine=engine) as writer:
            return ingest(input=second, session=writer, now=now)

    monkeypatch.setattr(module, "evaluate_case", evaluate)
    with ThreadPoolExecutor(max_workers=2) as executor:
        processing = executor.submit(
            process_case, case_id="case", engine=engine, now=now, models=[]
        )
        try:
            assert evaluating.wait(5)
            arrival = executor.submit(arrive)
            assert arriving.wait(5)
        finally:
            release.set()
        assert processing.result(timeout=5) is None
        assert arrival.result(timeout=5).sequence == 2
    with read_session(engine=engine) as check:
        assert check.get(CaseLog, "case").last_handled_sequence == 1
    assert pending_cases(engine=engine, now_us=0) == ["case"]
    process_case(case_id="case", engine=engine, now=now, models=[])
    assert pending_cases(engine=engine, now_us=0) == []
