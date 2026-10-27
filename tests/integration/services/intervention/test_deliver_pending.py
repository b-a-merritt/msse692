"""Delivery marks pending interventions sent once, in the same transaction that reads them."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from datetime import timezone
from threading import Barrier

from normative_conformance import models
from normative_conformance.database import read_session
from normative_conformance.database import write_session
from normative_conformance.services.intervention.deliver_pending import deliver_pending
from normative_conformance.services.intervention.list_intervention_records import (
    list_intervention_records,
)


def test_pending_interventions_are_returned_sent_once(*, session, engine):
    session.add(models.ConversationCase(case_id="case", created_at_us=0))
    session.flush()
    session.add(
        models.TargetAssignment(
            case_id="case", target_revision=1, assigned_at_us=0, speaker_id="configured-subject"
        )
    )
    session.add(
        models.Observation(
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
        )
    )
    session.flush()
    assessment = models.Assessment(
        case_id="case",
        target_revision=1,
        model_id="jev-1.14.0",
        prompt_version="conversation-1",
        evaluated_at_us=100_000_000,
        completed_at_us=101_000_000,
        after_sequence=0,
        through_sequence=1,
        action="intervene",
        action_confidence=0.9,
        selection_threshold=0.7,
        request_json="{}",
    )
    session.add(assessment)
    session.flush()
    intervention = models.Intervention(
        assessment_id=assessment.assessment_id, message="Feedback", created_at_us=102_000_000
    )
    session.add(intervention)
    session.commit()
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
    with read_session(engine=engine) as check:
        assert list_intervention_records(session=check) == delivered
    with write_session(engine=engine) as operation_session:
        assert (
            deliver_pending(
                case_id="case",
                session=operation_session,
                now=lambda: datetime.fromtimestamp(111, timezone.utc),
            )
            == []
        )


def test_concurrent_delivery_returns_each_intervention_once(*, session, engine):
    session.add(models.ConversationCase(case_id="case", created_at_us=0))
    session.flush()
    session.add(
        models.TargetAssignment(
            case_id="case", target_revision=1, assigned_at_us=0, speaker_id="configured-subject"
        )
    )
    session.add(
        models.Observation(
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
        )
    )
    session.flush()
    assessment = models.Assessment(
        case_id="case",
        target_revision=1,
        model_id="jev-1.14.0",
        prompt_version="conversation-1",
        evaluated_at_us=100_000_000,
        completed_at_us=101_000_000,
        after_sequence=0,
        through_sequence=1,
        action="intervene",
        action_confidence=0.9,
        selection_threshold=0.7,
        request_json="{}",
    )
    session.add(assessment)
    session.flush()
    intervention = models.Intervention(
        assessment_id=assessment.assessment_id, message="Feedback", created_at_us=102_000_000
    )
    session.add(intervention)
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

    assert sorted(len(batch) for batch in batches) == [0, 1]
    assert [record.intervention_id for batch in batches for record in batch] == [
        intervention.intervention_id
    ]
