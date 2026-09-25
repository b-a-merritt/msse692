"""Each test gets a real migrated SQLite database in its own temporary directory."""

import pytest
from sqlmodel import Session

from normative_conformance import models
from normative_conformance.database import create_database_engine
from normative_conformance.database import initialize_database


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

    intervention = models.Intervention(
        assessment_id=assessment.assessment_id,
        message="Feedback",
        created_at_us=12,
    )
    session.add(intervention)
    session.commit()
    session.expunge_all()
    return {
        "experiment": experiment,
        "case": case,
        "observation": observation,
        "model": model,
        "assessment": assessment,
        "intervention": intervention,
    }
