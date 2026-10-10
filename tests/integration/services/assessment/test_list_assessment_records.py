from datetime import datetime
from datetime import timezone
from itertools import count
from uuid import uuid4

from normative_conformance import models
from normative_conformance.database import read_session
from normative_conformance.services.assessment.check_repairs import check_repairs
from normative_conformance.services.assessment.evaluate_case import evaluate_case
from normative_conformance.services.assessment.list_assessment_records import (
    list_assessment_records,
)
from normative_conformance.services.model.list_models import list_models
from normative_conformance.services.scheduler.state import SchedulerState

from ...storage import persist


def test_no_assessments_returns_empty_records_without_experiment_configuration(*, session):
    assert list_assessment_records(case_id="missing", session=session) == []


def test_records_preserve_each_assessments_prefix_explanation_and_deadline(
    *, session, engine, assessment_queue
):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)
    scheduler = SchedulerState(queue=assessment_queue)

    first = persist(
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
    pending = evaluate_case(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        now=lambda: datetime.fromtimestamp(100, timezone.utc),
        scheduler=scheduler,
        models=evaluation_models,
    )[0]
    second = persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=32_000_000,
            end_at_us=33_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    resolution = check_repairs(
        case_id="case",
        evaluation_id=uuid4(),
        engine=engine,
        now=lambda: datetime.fromtimestamp(110, timezone.utc),
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
            start_at_us=34_000_000,
            end_at_us=35_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )

    records = list_assessment_records(case_id="case", session=session)

    assert [record.assessment_id for record in records] == [
        pending.assessment_id,
        resolution.assessment_id,
    ]
    assert [record.resolves_assessment_id for record in records] == [None, pending.assessment_id]
    assert [record.extent.observation_ids for record in records] == [
        [first.observation_id],
        [first.observation_id, second.observation_id],
    ]
    assert [record.extent.through_sequence for record in records] == [1, 2]
    assert [record.extent.observation_count for record in records] == [1, 2]
    assert [record.status for record in records] == ["pending", "conformant"]
    assert [record.explanation.reason_code for record in records] == ["awaiting_repair", "matched"]
    assert [record.evaluated_at for record in records] == [
        datetime.fromtimestamp(100, timezone.utc),
        datetime.fromtimestamp(110, timezone.utc),
    ]
    assert [record.next_due_at for record in records] == [
        datetime.fromtimestamp(110, timezone.utc),
        None,
    ]
    assert {record.subject_speaker_id for record in records} == {"configured-subject"}
