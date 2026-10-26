import json
from datetime import datetime
from datetime import timezone
from importlib import import_module
from threading import Event
from threading import Thread

import pytest
from sqlmodel import select

from normative_conformance.database import read_session
from normative_conformance.models.assessment import Assessment
from normative_conformance.models.case import CaseLog
from normative_conformance.models.intervention import Intervention
from normative_conformance.models.normative_model import NormativeModelVersion
from normative_conformance.models.observation import Observation
from normative_conformance.services.model.list_models import list_models
from normative_conformance.services.scheduler.run_worker.process_case import process_case

module = import_module("normative_conformance.services.scheduler.run_worker.run_worker")


@pytest.mark.parametrize("restart", [False, True])
def test_worker_polls_stored_speech_and_recovers_deadlines_without_new_input(
    engine, session, monkeypatch, restart
):
    session.add(CaseLog(case_id="case", created_at_us=0, target_speaker_id="A"))
    session.add(
        NormativeModelVersion(
            model_id="harm_phrase",
            version="poll-test",
            name="Test",
            type="undesired",
            repair_allowance_us=10,
            parameters_json="{}",
            rules_json=json.dumps(
                [
                    {
                        "rule_id": "word",
                        "description": "",
                        "sql": "SELECT 1 FROM observation WHERE case_id = :case_id AND "
                        "speaker_id = :subject_speaker_id AND sequence <= :through_sequence",
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
            transcript="hello",
            signal_level_min=-40,
            signal_level_avg=-30,
            signal_level_max=-20,
        )
    )
    session.commit()
    models = [m for m in list_models(session=session) if m.version == "poll-test"]
    session.rollback()
    clock_us = 100

    def now():
        return datetime(1970, 1, 1, microsecond=clock_us, tzinfo=timezone.utc)

    if restart:
        process_case(case_id="case", engine=engine, now=now, models=models)
        clock_us = 110
    stopped = Event()
    delivered = Event()
    original_process = module.process_case
    original_interventions = module.create_due_interventions

    def process(**kwargs):
        nonlocal clock_us
        opened = original_process(**kwargs)
        clock_us = 120 if opened is not None else 110
        return opened

    def interventions(**kwargs):
        original_interventions(**kwargs)
        with read_session(engine=engine) as check:
            if check.exec(select(Intervention)).first() is not None:
                stopped.set()
                delivered.set()

    monkeypatch.setattr(module, "process_case", process)
    monkeypatch.setattr(module, "create_due_interventions", interventions)
    worker = Thread(
        target=module.run_worker,
        kwargs={
            "stopped": stopped,
            "engine": engine,
            "now": now,
            "intervention_window_us": 5,
            "models": models,
        },
    )
    worker.start()
    try:
        assert delivered.wait(5)
    finally:
        stopped.set()
        worker.join(5)
    assert not worker.is_alive()
    with read_session(engine=engine) as check:
        rows = check.exec(select(Assessment).order_by(Assessment.assessment_id)).all()
        assert [row.status for row in rows] == ["pending", "conformant"]
        assert rows[1].resolves_assessment_id == rows[0].assessment_id
        assert check.get(CaseLog, "case").last_handled_sequence == 1
        assert len(check.exec(select(Intervention)).all()) == 1
