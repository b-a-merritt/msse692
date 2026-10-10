from datetime import datetime
from datetime import timezone
from itertools import count
from uuid import uuid4

import pytest
from sqlmodel import select

from normative_conformance import models
from normative_conformance.database import read_session
from normative_conformance.models.assessment import Assessment
from normative_conformance.models.case import CaseLog
from normative_conformance.models.normative_model import NormativeModelVersion
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.assessment import CaseSnapshot
from normative_conformance.services.assessment.assess_model import assess_model
from normative_conformance.services.assessment.check_repairs import check_repairs
from normative_conformance.services.assessment.evaluate_case import evaluate_case
from normative_conformance.services.assessment.get_last_repair import get_last_repair
from normative_conformance.services.model.get_model import get_model
from normative_conformance.services.model.get_subject_speaker_id import get_subject_speaker_id
from normative_conformance.services.model.list_models import list_models
from normative_conformance.services.observation.get_case_sequence import get_case_sequence
from normative_conformance.services.scheduler.state import SchedulerState

from ...storage import persist


def test_finalized_match_is_not_repeated_before_repair(*, session, engine, assessment_queue):
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
    assert final.resolves_assessment_id == original.assessment_id
    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=2_000_000,
            end_at_us=3_500_000,
            received_at_us=111_000_000,
            transcript="stop that right now please",
            signal_level_min=-60.0,
            signal_level_avg=-16.0,
            signal_level_max=0.0,
        ),
    )
    assert (
        assess_model(
            model=get_model(model_id="high_intensity_address", version="1", session=session),
            snapshot=CaseSnapshot(
                case_id="case",
                evaluation_id=str(uuid4()),
                through_sequence=get_case_sequence(case_id="case", session=session),
                evaluated_at_us=111_000_000,
            ),
            subject_speaker_id=get_subject_speaker_id(session=session),
            last_repair=get_last_repair(case_id="case", session=session),
            session=session,
        ).assessment_id
        == final.assessment_id
    )
    assert len(session.exec(select(Assessment)).all()) == 2


def test_reuse_checks_original_evidence_when_resolution_includes_later_speech(
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
            start_at_us=3_000_000,
            end_at_us=4_500_000,
            received_at_us=109_000_000,
            transcript="stop it right now please",
            signal_level_min=-60.0,
            signal_level_avg=-16.0,
            signal_level_max=0.0,
        ),
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
    assert final.resolves_assessment_id == original.assessment_id
    assert original.through_sequence == 1
    assert final.through_sequence == 2

    # This late repair clears the original evidence, while the later speech still matches.
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
    new = assess_model(
        model=get_model(model_id="high_intensity_address", version="1", session=session),
        snapshot=CaseSnapshot(
            case_id="case",
            evaluation_id=str(uuid4()),
            through_sequence=get_case_sequence(case_id="case", session=session),
            evaluated_at_us=112_000_000,
        ),
        subject_speaker_id=get_subject_speaker_id(session=session),
        last_repair=get_last_repair(case_id="case", session=session),
        session=session,
    )

    assert new.assessment_id != final.assessment_id
    assert new.status == "pending"
    assert new.next_due_at_us == 122_000_000


@pytest.mark.parametrize("repair_allowance_us", [None, 5_000_000])
def test_reuse_is_specific_to_model_and_version(
    *, session, engine, assessment_queue, repair_allowance_us
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
            end_at_us=1_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    identities = [("always", "1"), ("always", "2"), ("other", "1")]
    for model_id, version in identities:
        session.add(
            NormativeModelVersion(
                model_id=model_id,
                version=version,
                name=model_id,
                type="undesired",
                repair_allowance_us=repair_allowance_us,
                rules_json='[{"rule_id":"always","description":"Always matches","sql":"SELECT 1"}]',
                parameters_json="{}",
            )
        )
    session.commit()
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    originals = {
        (row.model_id, row.model_version): row
        for row in evaluate_case(
            case_id="case",
            evaluation_id=uuid4(),
            engine=engine,
            now=lambda: datetime.fromtimestamp(100, timezone.utc),
            scheduler=scheduler,
            models=evaluation_models,
        )
    }

    for model_id, version in identities:
        reused = assess_model(
            model=get_model(model_id=model_id, version=version, session=session),
            snapshot=CaseSnapshot(
                case_id="case",
                evaluation_id=str(uuid4()),
                through_sequence=get_case_sequence(case_id="case", session=session),
                evaluated_at_us=105_000_000,
            ),
            subject_speaker_id=get_subject_speaker_id(session=session),
            last_repair=get_last_repair(case_id="case", session=session),
            session=session,
        )
        assert reused.model_dump() == originals[model_id, version].model_dump()

    assert len(session.exec(select(Assessment)).all()) == 3


def test_unresolved_pending_takes_precedence_over_a_later_result(
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
    later = Assessment(
        **(
            pending.model_dump()
            | {
                "assessment_id": None,
                "evaluation_id": "later",
                "status": "conformant",
                "next_due_at_us": None,
            }
        )
    )
    session.add(later)
    session.commit()

    assert (
        assess_model(
            model=get_model(model_id="high_intensity_address", version="1", session=session),
            snapshot=CaseSnapshot(
                case_id="case",
                evaluation_id=str(uuid4()),
                through_sequence=get_case_sequence(case_id="case", session=session),
                evaluated_at_us=105_000_000,
            ),
            subject_speaker_id=get_subject_speaker_id(session=session),
            last_repair=get_last_repair(case_id="case", session=session),
            session=session,
        ).assessment_id
        == pending.assessment_id
    )


def test_reuse_is_specific_to_the_case(*, session, engine, assessment_queue):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)
    scheduler = SchedulerState(queue=assessment_queue)

    observation = persist(
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
    session.add(CaseLog(case_id="other", created_at_us=0))
    session.flush()
    session.add(Observation(**(observation.model_dump() | {"case_id": "other"})))
    session.flush()
    session.add(
        Assessment(
            **(
                original.model_dump()
                | {"assessment_id": None, "evaluation_id": "other", "case_id": "other"}
            )
        )
    )
    session.commit()

    assert (
        assess_model(
            model=get_model(model_id="high_intensity_address", version="1", session=session),
            snapshot=CaseSnapshot(
                case_id="case",
                evaluation_id=str(uuid4()),
                through_sequence=get_case_sequence(case_id="case", session=session),
                evaluated_at_us=105_000_000,
            ),
            subject_speaker_id=get_subject_speaker_id(session=session),
            last_repair=get_last_repair(case_id="case", session=session),
            session=session,
        ).assessment_id
        == original.assessment_id
    )
