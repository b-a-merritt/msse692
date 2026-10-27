from datetime import datetime
from datetime import timezone
from importlib import import_module
from threading import Event
from threading import Thread

from sqlmodel import select

from normative_conformance.database import read_session
from normative_conformance.models.assessment import Assessment
from normative_conformance.models.case import CaseLog
from normative_conformance.models.case import TargetAssignment
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.decision import DecisionAnswers
from normative_conformance.schemas.decision import ObservationAnswers

module = import_module("normative_conformance.services.scheduler.run_worker.run_worker")
process_case_module = import_module(
    "normative_conformance.services.scheduler.run_worker.process_case"
)


def test_worker_assesses_stored_speech_and_advances_progress(engine, session, monkeypatch):
    session.add(CaseLog(case_id="case", created_at_us=0))
    session.flush()
    session.add(
        TargetAssignment(case_id="case", target_revision=1, assigned_at_us=0, speaker_id="A")
    )
    session.add(
        Observation(
            case_id="case",
            observation_id="one",
            sequence=1,
            received_at_us=0,
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
    session.rollback()

    def evaluate(*, snapshot, client):
        assert snapshot.new_observation_ids == ["one"]
        result = DecisionAnswers(
            model="jev-1.14.0",
            prompt_version="conversation-1",
            observations=[
                ObservationAnswers(
                    observation_id="one",
                    topic_scores={"chores": 0.1},
                    primary_topic="unknown",
                    behavior_scores={"swearing": 0.1},
                    intensity=0.0,
                )
            ],
            action="remain_silent",
            action_probabilities={"remain_silent": 1.0},
            action_confidence=1.0,
        )
        return result, '{"request": "fake"}'

    stopped = Event()
    processed = Event()
    original_process = module.process_case

    def process(**kwargs):
        original_process(**kwargs)
        processed.set()
        stopped.set()

    monkeypatch.setattr(process_case_module.jev, "evaluate", evaluate)
    monkeypatch.setattr(module, "process_case", process)
    worker = Thread(
        target=module.run_worker,
        kwargs={
            "stopped": stopped,
            "engine": engine,
            "now": lambda: datetime(1970, 1, 1, tzinfo=timezone.utc),
            "client": object(),
            "batch_size": 4,
            "context_seconds": 30,
        },
    )
    worker.start()
    try:
        assert processed.wait(5)
    finally:
        stopped.set()
        worker.join(5)
    assert not worker.is_alive()
    with read_session(engine=engine) as check:
        rows = check.exec(select(Assessment)).all()
        assert [(row.through_sequence, row.action) for row in rows] == [(1, "remain_silent")]
        assert check.get(CaseLog, "case").last_handled_sequence == 1
