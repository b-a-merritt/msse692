"""Intervention reads filter by case and delivery status without changing records."""

from datetime import datetime
from datetime import timezone
from itertools import count

from sqlmodel import select

from normative_conformance import models
from normative_conformance.database import write_session
from normative_conformance.services.intervention.create_intervention import create_intervention
from normative_conformance.services.intervention.list_intervention_records import (
    list_intervention_records,
)
from normative_conformance.services.intervention.list_interventions import list_interventions

from ...storage import persist


def test_no_interventions_returns_an_empty_list(*, session):
    assert list_intervention_records(session=session) == []


def test_interventions_are_listed_in_id_order_with_sorted_sources(*, session, engine):
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
    later = [
        persist(
            session=session,
            record=models.Assessment(
                evaluation_id=f"evaluation-{next(assessment_ids)}",
                case_id="case",
                model_id="high_intensity_address",
                model_version="1",
                evaluated_at_us=103_000_000,
                through_sequence=1,
                status="conformant",
                explanation_json="{}",
            ),
        ),
        persist(
            session=session,
            record=models.Assessment(
                evaluation_id=f"evaluation-{next(assessment_ids)}",
                case_id="case",
                model_id="repeated_interruption",
                model_version="1",
                evaluated_at_us=103_000_000,
                through_sequence=1,
                status="conformant",
                explanation_json="{}",
            ),
        ),
    ]
    with write_session(engine=engine) as operation_session:
        create_intervention(
            case_id="case",
            since_us=103_000_000,
            session=operation_session,
            now=lambda: datetime.fromtimestamp(105, timezone.utc),
        )

    records = list_intervention_records(session=session)
    assert [record.assessment_ids for record in records] == [
        [first.assessment_id],
        [assessment.assessment_id for assessment in later],
    ]
    assert [record.created_at for record in records] == [
        datetime.fromtimestamp(102, timezone.utc),
        datetime.fromtimestamp(105, timezone.utc),
    ]


def test_status_is_derived_from_the_sent_time(*, session, engine):
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
    with write_session(engine=engine) as operation_session:
        create_intervention(
            case_id="case",
            since_us=100_000_000,
            session=operation_session,
            now=lambda: datetime.fromtimestamp(102, timezone.utc),
        )
    sent = list_interventions(session=session)[0]
    persist(
        session=session,
        record=models.Assessment(
            evaluation_id=f"evaluation-{next(assessment_ids)}",
            case_id="case",
            model_id="extended_turn",
            model_version="1",
            evaluated_at_us=103_000_000,
            through_sequence=1,
            status="conformant",
            explanation_json="{}",
        ),
    )
    with write_session(engine=engine) as operation_session:
        create_intervention(
            case_id="case",
            since_us=103_000_000,
            session=operation_session,
            now=lambda: datetime.fromtimestamp(105, timezone.utc),
        )
    pending = list_interventions(session=session)[-1]
    sent.sent_at_us = 106_000_000
    session.commit()

    assert [
        (record.intervention_id, record.status, record.sent_at)
        for record in list_intervention_records(session=session)
    ] == [
        (sent.intervention_id, "sent", datetime.fromtimestamp(106, timezone.utc)),
        (pending.intervention_id, "pending", None),
    ]
    assert [
        record.intervention_id
        for record in list_intervention_records(status="sent", session=session)
    ] == [sent.intervention_id]
    assert [
        record.intervention_id
        for record in list_intervention_records(status="pending", session=session)
    ] == [pending.intervention_id]


def test_filters_by_case_and_ids(*, session, engine):
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
    with write_session(engine=engine) as operation_session:
        create_intervention(
            case_id="case",
            since_us=100_000_000,
            session=operation_session,
            now=lambda: datetime.fromtimestamp(102, timezone.utc),
        )
    record = list_intervention_records(session=session)[0]
    assert list_intervention_records(case_id="case", session=session) == [record]
    assert list_intervention_records(case_id="other", session=session) == []
    assert list_intervention_records(
        intervention_ids=[record.intervention_id], session=session
    ) == [record]
    assert (
        list_intervention_records(intervention_ids=[record.intervention_id + 1], session=session)
        == []
    )
    assert list_intervention_records(intervention_ids=[], session=session) == []


def test_listing_does_not_mark_interventions_sent(*, session, engine):
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
    with write_session(engine=engine) as operation_session:
        create_intervention(
            case_id="case",
            since_us=100_000_000,
            session=operation_session,
            now=lambda: datetime.fromtimestamp(102, timezone.utc),
        )
    list_intervention_records(session=session)
    assert [row.sent_at_us for row in session.exec(select(models.Intervention))] == [None]
