"""Delivery marks pending interventions sent once, in the same transaction that reads them."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from datetime import timezone
from itertools import count
from threading import Barrier
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import OperationalError

from normative_conformance import models
from normative_conformance.database import write_session
from normative_conformance.errors import StorageUnavailable
from normative_conformance.services.intervention.create_intervention import create_intervention
from normative_conformance.services.intervention.deliver_pending import deliver_pending
from normative_conformance.services.intervention.list_intervention_records import (
    list_intervention_records,
)

from ...storage import persist


def test_nothing_pending_returns_an_empty_list(*, engine):
    with write_session(engine=engine) as operation_session:
        assert (
            deliver_pending(
                case_id="case",
                session=operation_session,
                now=lambda: datetime.fromtimestamp(110, timezone.utc),
            )
            == []
        )


def test_pending_interventions_are_returned_sent_once(*, session, engine):
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
    pending = list_intervention_records(session=session)[0]
    session.commit()

    with write_session(engine=engine) as operation_session:
        delivered = deliver_pending(
            case_id="case",
            session=operation_session,
            now=lambda: datetime.fromtimestamp(110, timezone.utc),
        )
    assert delivered == [
        pending.model_copy(
            update={"status": "sent", "sent_at": datetime.fromtimestamp(110, timezone.utc)}
        )
    ]
    assert list_intervention_records(session=session) == delivered
    with write_session(engine=engine) as operation_session:
        assert (
            deliver_pending(
                case_id="case",
                session=operation_session,
                now=lambda: datetime.fromtimestamp(111, timezone.utc),
            )
            == []
        )


def test_sent_interventions_are_excluded(*, session, engine):
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
    with write_session(engine=engine) as operation_session:
        deliver_pending(
            case_id="case",
            session=operation_session,
            now=lambda: datetime.fromtimestamp(110, timezone.utc),
        )
    persist(
        session=session,
        record=models.Assessment(
            evaluation_id=f"evaluation-{next(assessment_ids)}",
            case_id="case",
            model_id="extended_turn",
            model_version="1",
            evaluated_at_us=111_000_000,
            through_sequence=1,
            status="conformant",
            explanation_json="{}",
        ),
    )
    with write_session(engine=engine) as operation_session:
        create_intervention(
            case_id="case",
            since_us=111_000_000,
            session=operation_session,
            now=lambda: datetime.fromtimestamp(112, timezone.utc),
        )
    second = list_intervention_records(status="pending", session=session)[0]
    session.commit()

    with write_session(engine=engine) as operation_session:
        assert [
            record.intervention_id
            for record in deliver_pending(
                case_id="case",
                session=operation_session,
                now=lambda: datetime.fromtimestamp(113, timezone.utc),
            )
        ] == [second.intervention_id]
    assert [record.sent_at for record in list_intervention_records(session=session)] == [
        datetime.fromtimestamp(110, timezone.utc),
        datetime.fromtimestamp(113, timezone.utc),
    ]


def test_delivery_leaves_other_cases_pending(*, session, engine):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="delivered-case", created_at_us=0))
    session.add(models.CaseLog(case_id="other-case", created_at_us=0))
    session.commit()
    for case_id in ["delivered-case", "other-case"]:
        persist(
            session=session,
            record=models.Observation(
                case_id=case_id,
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
        persist(
            session=session,
            record=models.Assessment(
                evaluation_id=f"evaluation-{case_id}",
                case_id=case_id,
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
                case_id=case_id,
                since_us=100_000_000,
                session=operation_session,
                now=lambda: datetime.fromtimestamp(102, timezone.utc),
            )
    session.commit()

    with write_session(engine=engine) as operation_session:
        delivered = deliver_pending(
            case_id="delivered-case",
            session=operation_session,
            now=lambda: datetime.fromtimestamp(110, timezone.utc),
        )

    assert [record.case_id for record in delivered] == ["delivered-case"]
    assert [
        (record.case_id, record.status) for record in list_intervention_records(session=session)
    ] == [("delivered-case", "sent"), ("other-case", "pending")]


def test_failure_before_commit_leaves_interventions_pending(*, session, engine, monkeypatch):
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

    with write_session(engine=engine) as delivery_session:
        monkeypatch.setattr(
            delivery_session,
            "commit",
            Mock(side_effect=OperationalError("COMMIT", {}, Exception("disk I/O error"))),
        )
        with pytest.raises(StorageUnavailable, match="The interventions could not be delivered"):
            deliver_pending(
                case_id="case",
                session=delivery_session,
                now=lambda: datetime.fromtimestamp(110, timezone.utc),
            )

    assert [record.status for record in list_intervention_records(session=session)] == ["pending"]


def test_concurrent_delivery_returns_each_intervention_once(*, session, engine):
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
    pending = list_intervention_records(session=session)
    session.commit()
    start = Barrier(2)

    def deliver_together():
        start.wait(timeout=5)
        with write_session(engine=engine) as operation_session:
            return deliver_pending(
                case_id="case",
                session=operation_session,
                now=lambda: datetime.fromtimestamp(110, timezone.utc),
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(deliver_together) for _ in range(2)]
        batches = [future.result(timeout=10) for future in futures]

    assert sorted(len(batch) for batch in batches) == [0, 2]
    assert sorted(record.intervention_id for batch in batches for record in batch) == [
        record.intervention_id for record in pending
    ]
    assert all(
        record.sent_at == datetime.fromtimestamp(110, timezone.utc)
        for batch in batches
        for record in batch
    )
