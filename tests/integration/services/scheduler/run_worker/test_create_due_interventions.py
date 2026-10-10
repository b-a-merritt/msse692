from uuid import uuid4

import pytest

from normative_conformance import models
from normative_conformance.services import intervention
from normative_conformance.services.scheduler.run_worker.create_due_interventions import (
    create_due_interventions,
)
from normative_conformance.timestamps import from_microseconds

from ....storage import persist
from ....storage import persist_in_database


@pytest.mark.parametrize("current_time_us", [101_999_999, 102_000_000, 103_000_000])
def test_window_creates_one_intervention_only_when_due(*, engine, session, current_time_us):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    persist(
        session=session,
        record=models.Observation(
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

    persist_in_database(
        engine=engine,
        record=models.Assessment(
            evaluation_id=str(uuid4()),
            case_id="case",
            model_id="harm_phrase",
            model_version="1",
            evaluated_at_us=100_000_000,
            through_sequence=1,
            status="conformant",
            explanation_json="{}",
        ),
    )
    intervention_windows = {"case": 100_000_000}

    for _ in range(2):
        create_due_interventions(
            intervention_windows=intervention_windows,
            intervention_window_us=2_000_000,
            engine=engine,
            now=lambda: from_microseconds(value=current_time_us),
        )

    due = current_time_us >= 102_000_000
    assert intervention_windows == ({} if due else {"case": 100_000_000})
    assert len(intervention.list_intervention_records(session=session)) == int(due)


def test_failed_decision_consumes_its_window_and_other_cases_continue(
    *, engine, session, monkeypatch
):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    persist(
        session=session,
        record=models.Observation(
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

    persist_in_database(
        engine=engine,
        record=models.Assessment(
            evaluation_id=str(uuid4()),
            case_id="case",
            model_id="harm_phrase",
            model_version="1",
            evaluated_at_us=100_000_000,
            through_sequence=1,
            status="conformant",
            explanation_json="{}",
        ),
    )
    intervention_windows = {"failing": 100_000_000, "case": 100_000_000, "future": 102_000_000}
    decided = []
    original = intervention.create_intervention

    def create_intervention(*, case_id, since_us, session, now):
        assert case_id not in intervention_windows
        decided.append(case_id)
        if case_id == "failing":
            raise RuntimeError("Intervention failed")
        original(case_id=case_id, since_us=since_us, session=session, now=now)

    monkeypatch.setattr(intervention, "create_intervention", create_intervention)
    for _ in range(2):
        create_due_interventions(
            intervention_windows=intervention_windows,
            intervention_window_us=2_000_000,
            engine=engine,
            now=lambda: from_microseconds(value=102_000_000),
        )

    assert intervention_windows == {"future": 102_000_000}
    assert decided == ["failing", "case"]
    assert len(intervention.list_intervention_records(session=session)) == 1
