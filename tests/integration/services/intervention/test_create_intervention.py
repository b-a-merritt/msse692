"""Interventions group newly confirmed undesired matches under one fixed message."""

from datetime import datetime
from datetime import timezone
from itertools import count

import pytest
from sqlmodel import select

from normative_conformance import models
from normative_conformance.database import write_session
from normative_conformance.errors import StorageUnavailable
from normative_conformance.services.intervention.create_intervention import create_intervention
from normative_conformance.services.intervention.list_interventions import list_interventions
from normative_conformance.services.model.list_models import list_models

from ...storage import persist

INTERRUPTION = "You've interrupted several times. Let them finish before you respond."
TALKING_OVER = "You're talking over them with a raised voice. Pause and let them finish."
THREAT = "You said something that could be heard as a threat. Take a moment before you continue."


def test_single_match_creates_a_pending_intervention(*, session, engine):
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
    assessment_ids = count(1)

    assessment = persist(
        session=session,
        record=models.Assessment(
            evaluation_id=f"evaluation-{next(assessment_ids)}",
            case_id="case",
            model_id="repeated_interruption",
            model_version="1",
            evaluated_at_us=100_000_000,
            through_sequence=1,
            status="conformant",
            explanation_json="{}",
        ),
    )
    with write_session(engine=engine) as operation_session:
        assert (
            create_intervention(
                case_id="case",
                since_us=100_000_000,
                session=operation_session,
                now=lambda: datetime.fromtimestamp(102, timezone.utc),
            )
            is None
        )
    row = session.exec(select(models.Intervention)).one()
    assert row.model_dump() == {
        "intervention_id": row.intervention_id,
        "case_id": "case",
        "message": INTERRUPTION,
        "created_at_us": 102_000_000,
        "sent_at_us": None,
    }
    assert session.exec(select(models.InterventionSource)).one().model_dump() == {
        "intervention_id": row.intervention_id,
        "assessment_id": assessment.assessment_id,
    }


@pytest.mark.parametrize(
    ("model_ids", "message"),
    [
        pytest.param(
            ["repeated_interruption", "high_intensity_address"], TALKING_OVER, id="listed"
        ),
        pytest.param(
            ["repeated_interruption", "high_intensity_address", "extended_turn"],
            TALKING_OVER,
            id="listed-with-extra",
        ),
        pytest.param(["extended_turn", "harm_phrase"], THREAT, id="unlisted"),
    ],
)
def test_matches_share_one_message(*, session, engine, model_ids, message):
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
    assessment_ids = count(1)

    assessments = [
        persist(
            session=session,
            record=models.Assessment(
                evaluation_id=f"evaluation-{next(assessment_ids)}",
                case_id="case",
                model_id=model_id,
                model_version="1",
                evaluated_at_us=100_500_000,
                through_sequence=1,
                status="conformant",
                explanation_json="{}",
            ),
        )
        for model_id in model_ids
    ]
    with write_session(engine=engine) as operation_session:
        create_intervention(
            case_id="case",
            since_us=100_000_000,
            session=operation_session,
            now=lambda: datetime.fromtimestamp(102, timezone.utc),
        )
    row = session.exec(select(models.Intervention)).one()
    assert row.message == message
    assert {
        (source.intervention_id, source.assessment_id)
        for source in session.exec(select(models.InterventionSource))
    } == {(row.intervention_id, assessment.assessment_id) for assessment in assessments}


def test_every_undesired_model_has_its_own_message(*, session, engine):
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
    assessment_ids = count(1)

    for model in list_models(session=session):
        if model.type != "undesired":
            continue
        persist(
            session=session,
            record=models.Assessment(
                evaluation_id=f"evaluation-{next(assessment_ids)}",
                case_id="case",
                model_id=model.model_id,
                model_version="1",
                evaluated_at_us=100_000_000,
                through_sequence=1,
                status="conformant",
                explanation_json="{}",
            ),
        )
        with write_session(engine=engine) as operation_session:
            create_intervention(
                case_id="case",
                since_us=100_000_000,
                session=operation_session,
                now=lambda: datetime.fromtimestamp(102, timezone.utc),
            )
        assert list_interventions(session=session)[-1].message


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"at": 99.999999}, id="before-window"),
        pytest.param({"status": "pending"}, id="pending"),
        pytest.param({"status": "non-conformant"}, id="repaired"),
        pytest.param({"model_id": "apology"}, id="repair-model"),
    ],
)
def test_ineligible_assessments_create_nothing(*, session, engine, changes):
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
    assessment_ids = count(1)

    persist(
        session=session,
        record=models.Assessment(
            evaluation_id=f"evaluation-{next(assessment_ids)}",
            case_id="case",
            model_id=({"model_id": "harm_phrase"} | changes).get("model_id", "harm_phrase"),
            model_version="1",
            evaluated_at_us=round(
                ({"model_id": "harm_phrase"} | changes).get("at", 100) * 1_000_000
            ),
            through_sequence=1,
            status=({"model_id": "harm_phrase"} | changes).get("status", "conformant"),
            explanation_json="{}",
        ),
    )
    with write_session(engine=engine) as operation_session:
        assert (
            create_intervention(
                case_id="case",
                since_us=100_000_000,
                session=operation_session,
                now=lambda: datetime.fromtimestamp(102, timezone.utc),
            )
            is None
        )
    assert session.exec(select(models.Intervention)).all() == []


def test_other_cases_are_excluded(*, session, engine):
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
    assessment_ids = count(1)

    session.add(models.CaseLog(case_id="other", created_at_us=0))
    session.add(
        models.Observation(
            case_id="other",
            observation_id="1",
            sequence=1,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=1,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        )
    )
    session.commit()
    persist(
        session=session,
        record=models.Assessment(
            evaluation_id=f"evaluation-{next(assessment_ids)}",
            case_id="other",
            model_id="harm_phrase",
            model_version="1",
            evaluated_at_us=100_000_000,
            through_sequence=1,
            status="conformant",
            explanation_json="{}",
        ),
    )
    with write_session(engine=engine) as operation_session:
        assert (
            create_intervention(
                case_id="case",
                since_us=100_000_000,
                session=operation_session,
                now=lambda: datetime.fromtimestamp(102, timezone.utc),
            )
            is None
        )


def test_linked_assessments_are_not_decided_again(*, session, engine):
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
    assessment_ids = count(1)

    first = persist(
        session=session,
        record=models.Assessment(
            evaluation_id=f"evaluation-{next(assessment_ids)}",
            case_id="case",
            model_id="harm_phrase",
            model_version="1",
            evaluated_at_us=100_000_000,
            through_sequence=1,
            status="conformant",
            explanation_json="{}",
        ),
    )
    with write_session(engine=engine) as operation_session:
        create_intervention(
            case_id="case",
            since_us=100_000_000,
            session=operation_session,
            now=lambda: datetime.fromtimestamp(102, timezone.utc),
        )
    with write_session(engine=engine) as operation_session:
        create_intervention(
            case_id="case",
            since_us=100_000_000,
            session=operation_session,
            now=lambda: datetime.fromtimestamp(102, timezone.utc),
        )
    assert len(list_interventions(session=session)) == 1
    second = persist(
        session=session,
        record=models.Assessment(
            evaluation_id=f"evaluation-{next(assessment_ids)}",
            case_id="case",
            model_id="extended_turn",
            model_version="1",
            evaluated_at_us=101_000_000,
            through_sequence=1,
            status="conformant",
            explanation_json="{}",
        ),
    )
    with write_session(engine=engine) as operation_session:
        create_intervention(
            case_id="case",
            since_us=100_000_000,
            session=operation_session,
            now=lambda: datetime.fromtimestamp(102, timezone.utc),
        )
    rows = list_interventions(session=session)
    assert len(rows) == 2
    assert {
        (source.intervention_id, source.assessment_id)
        for source in session.exec(select(models.InterventionSource))
    } == {
        (rows[0].intervention_id, first.assessment_id),
        (rows[1].intervention_id, second.assessment_id),
    }


def test_missing_message_fails_without_storing(*, session, engine):
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
    assessment_ids = count(1)

    session.add(
        models.NormativeModelVersion(
            model_id="unlisted",
            name="Unlisted",
            version="1",
            rules_json='[{"rule_id":"test"}]',
            parameters_json="{}",
        )
    )
    session.commit()
    persist(
        session=session,
        record=models.Assessment(
            evaluation_id=f"evaluation-{next(assessment_ids)}",
            case_id="case",
            model_id="unlisted",
            model_version="1",
            evaluated_at_us=100_000_000,
            through_sequence=1,
            status="conformant",
            explanation_json="{}",
        ),
    )
    with (
        pytest.raises(LookupError, match="No intervention message matches the assessments"),
        write_session(engine=engine) as operation_session,
    ):
        create_intervention(
            case_id="case",
            since_us=100_000_000,
            session=operation_session,
            now=lambda: datetime.fromtimestamp(102, timezone.utc),
        )
    assert session.exec(select(models.Intervention)).all() == []


def test_storage_failure_rolls_back(*, session, engine):
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
    assessment_ids = count(1)

    persist(
        session=session,
        record=models.Assessment(
            evaluation_id=f"evaluation-{next(assessment_ids)}",
            case_id="case",
            model_id="harm_phrase",
            model_version="1",
            evaluated_at_us=100_000_000,
            through_sequence=1,
            status="conformant",
            explanation_json="{}",
        ),
    )
    session.connection().exec_driver_sql("""
        CREATE TRIGGER fail_source BEFORE INSERT ON intervention_source
        BEGIN SELECT RAISE(ABORT, 'Source storage failed'); END
    """)
    session.commit()
    with (
        pytest.raises(StorageUnavailable, match="The intervention could not be created"),
        write_session(engine=engine) as operation_session,
    ):
        create_intervention(
            case_id="case",
            since_us=100_000_000,
            session=operation_session,
            now=lambda: datetime.fromtimestamp(102, timezone.utc),
        )
    assert session.exec(select(models.Intervention)).all() == []
    assert session.exec(select(models.InterventionSource)).all() == []
