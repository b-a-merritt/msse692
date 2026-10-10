from datetime import datetime
from datetime import timezone
from itertools import count
from uuid import uuid4

import pytest

from normative_conformance import models
from normative_conformance.database import read_session
from normative_conformance.models.assessment import Assessment
from normative_conformance.schemas.assessment import CaseSnapshot
from normative_conformance.schemas.assessment import Explanation
from normative_conformance.services.assessment.evaluate_case import evaluate_case
from normative_conformance.services.assessment.list_assessments import list_assessments
from normative_conformance.services.assessment.resolve_pending import resolve_pending
from normative_conformance.services.model.get_model import get_model
from normative_conformance.services.model.get_subject_speaker_id import get_subject_speaker_id
from normative_conformance.services.model.list_models import list_models
from normative_conformance.services.observation.get_case_sequence import get_case_sequence
from normative_conformance.services.scheduler.state import SchedulerState

from ...storage import persist


@pytest.mark.parametrize(
    "received,expected", [(109.999999, "non-conformant"), (110, "conformant"), (111, "conformant")]
)
def test_repair_uses_fixed_deadline_when_check_is_delayed(
    *, session, engine, assessment_queue, received, expected
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
    before = original.model_dump()
    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=1_000_000,
            end_at_us=2_000_000,
            received_at_us=round((received) * 1_000_000),
            transcript="I apologize",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    resolution = resolve_pending(
        pending=original,
        model=get_model(
            model_id=(original).model_id, version=(original).model_version, session=session
        ),
        repair_models=[model for model in list_models(session=session) if model.type == "repairs"],
        snapshot=CaseSnapshot(
            case_id="case",
            evaluation_id=str(uuid4()),
            through_sequence=get_case_sequence(case_id="case", session=session),
            evaluated_at_us=120_000_000,
        ),
        subject_speaker_id=get_subject_speaker_id(session=session),
        session=session,
    )
    assert resolution.resolves_assessment_id == original.assessment_id
    assert resolution.status == expected
    explanation = Explanation.model_validate_json(resolution.explanation_json)
    repaired = expected == "non-conformant"
    assert explanation.reason_code == ("repaired" if repaired else "matched")
    assert explanation.rules[0].outcome == ("not_satisfied" if repaired else "satisfied")
    assert explanation.rules[0].observation_ids == (["2"] if repaired else [])
    assert session.get(Assessment, original.assessment_id).model_dump() == before
    assert list_assessments(status="pending", unresolved=True, session=session) == []


def test_older_speech_arriving_later_does_not_cancel_pending(*, session, engine, assessment_queue):
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
            start_at_us=3_000_000,
            end_at_us=4_500_000,
            received_at_us=0,
            transcript="stop that right now please",
            signal_level_min=-60.0,
            signal_level_avg=-16.0,
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
    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=1_000_000,
            received_at_us=105_000_000,
            transcript="I apologize",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    assert (
        resolve_pending(
            pending=pending,
            model=get_model(
                model_id=(pending).model_id, version=(pending).model_version, session=session
            ),
            repair_models=[
                model for model in list_models(session=session) if model.type == "repairs"
            ],
            snapshot=CaseSnapshot(
                case_id="case",
                evaluation_id=str(uuid4()),
                through_sequence=get_case_sequence(case_id="case", session=session),
                evaluated_at_us=110_000_000,
            ),
            subject_speaker_id=get_subject_speaker_id(session=session),
            session=session,
        ).status
        == "conformant"
    )


def test_latest_late_repair_does_not_hide_earlier_timely_repair(
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
    pending = evaluate_case(
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
    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=3_000_000,
            end_at_us=4_000_000,
            received_at_us=115_000_000,
            transcript="I am sorry",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    assert (
        resolve_pending(
            pending=pending,
            model=get_model(
                model_id=(pending).model_id, version=(pending).model_version, session=session
            ),
            repair_models=[
                model for model in list_models(session=session) if model.type == "repairs"
            ],
            snapshot=CaseSnapshot(
                case_id="case",
                evaluation_id=str(uuid4()),
                through_sequence=get_case_sequence(case_id="case", session=session),
                evaluated_at_us=120_000_000,
            ),
            subject_speaker_id=get_subject_speaker_id(session=session),
            session=session,
        ).status
        == "non-conformant"
    )


def test_repair_checks_original_evidence_even_when_later_speech_matches(
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
    pending = evaluate_case(
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
            start_at_us=3_000_000,
            end_at_us=4_500_000,
            received_at_us=104_000_000,
            transcript="stop it right now please",
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
            end_at_us=2_000_000,
            received_at_us=105_000_000,
            transcript="I apologize",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )

    result = resolve_pending(
        pending=pending,
        model=get_model(
            model_id=(pending).model_id, version=(pending).model_version, session=session
        ),
        repair_models=[model for model in list_models(session=session) if model.type == "repairs"],
        snapshot=CaseSnapshot(
            case_id="case",
            evaluation_id=str(uuid4()),
            through_sequence=get_case_sequence(case_id="case", session=session),
            evaluated_at_us=105_000_000,
        ),
        subject_speaker_id=get_subject_speaker_id(session=session),
        session=session,
    )

    assert result.status == "non-conformant"
    assert result.resolves_assessment_id == pending.assessment_id
    assert pending.through_sequence == 1
    assert result.through_sequence == 3
