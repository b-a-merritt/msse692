"""Each test gets a real migrated SQLite database in its own temporary directory."""

from datetime import datetime
from datetime import timezone

import pytest
from sqlmodel import Session

from normative_conformance import models
from normative_conformance.database import create_database_engine
from normative_conformance.database import initialize_database
from normative_conformance.database import read_session
from normative_conformance.queue import create_assessment_queue
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.services.model.list_models import list_models
from normative_conformance.services.scheduler.state import SchedulerState


@pytest.fixture
def observation_data():
    return {
        "case_id": "case",
        "observation_id": "chunk",
        "speaker_id": "subject",
        "start_at": "2026-09-26T12:00:00.123456+03:00",
        "end_at": "2026-09-26T12:00:01.654321+03:00",
        "transcript": "  Hello!\n",
        "signal_level_min": -50.0,
        "signal_level_avg": -30.0,
        "signal_level_max": -10.0,
    }


@pytest.fixture
def observation_input(*, observation_data):
    return ObservationInput.model_validate(observation_data)


@pytest.fixture
def received_at():
    return datetime(2026, 9, 26, 9, 2, 3, 456789, tzinfo=timezone.utc)


@pytest.fixture
def assessment_queue(*, tmp_path):
    queue = create_assessment_queue(path=tmp_path / "queue")
    try:
        yield queue
    finally:
        queue.close()


@pytest.fixture
def scheduler(*, assessment_queue):
    return SchedulerState(queue=assessment_queue)


@pytest.fixture
def empty_engine(*, tmp_path):
    engine = create_database_engine(path=tmp_path / "test.sqlite3")
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def engine(*, empty_engine):
    initialize_database(engine=empty_engine)
    return empty_engine


@pytest.fixture
def model_catalog(*, engine):
    """The seeded catalog, as startup validation hands it to the worker."""
    with read_session(engine=engine) as session:
        return list_models(session=session)


@pytest.fixture
def session(*, engine):
    with Session(bind=engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
def records(*, session):
    experiment = models.ExperimentConfig(subject_speaker_id="subject", created_at_us=1)
    case = models.CaseLog(case_id="case", created_at_us=1)
    session.add_all([experiment, case])
    session.flush()

    observation = models.Observation(
        case_id="case",
        observation_id="chunk",
        sequence=1,
        received_at_us=10,
        speaker_id="subject",
        start_at_us=1,
        end_at_us=9,
        transcript="Hello",
        signal_level_min=-30.0,
        signal_level_avg=-20.0,
        signal_level_max=-10.0,
    )
    model = models.NormativeModelVersion(
        model_id="anger",
        name="Anger",
        version="1",
        rules_json='[{"rule_id":"test"}]',
        parameters_json="{}",
    )
    session.add_all([observation, model])
    session.flush()

    assessment = models.Assessment(
        evaluation_id="evaluation-1",
        case_id="case",
        model_id="anger",
        model_version="1",
        evaluated_at_us=11,
        through_sequence=1,
        status="conformant",
        explanation_json='{"reason_code":"satisfied"}',
    )
    session.add(assessment)
    session.flush()

    intervention = models.Intervention(case_id="case", message="Feedback", created_at_us=12)
    session.add(intervention)
    session.flush()

    intervention_source = models.InterventionSource(
        intervention_id=intervention.intervention_id,
        assessment_id=assessment.assessment_id,
    )
    session.add(intervention_source)
    session.commit()
    session.expunge_all()
    return {
        "experiment": experiment,
        "case": case,
        "observation": observation,
        "model": model,
        "assessment": assessment,
        "intervention": intervention,
        "intervention_source": intervention_source,
    }
