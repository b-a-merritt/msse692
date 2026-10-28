"""Intervention records combine stored interventions with their source assessments."""

from datetime import UTC
from datetime import datetime

from normative_conformance import models
from normative_conformance.services.intervention.list_intervention_records import (
    list_intervention_records,
)


def test_records_include_case_subject_source_and_delivery_status(*, session):
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
    assessments = [
        models.Assessment(
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
        for _ in range(2)
    ]
    session.add_all(assessments)
    session.flush()
    session.add_all(
        [
            models.Intervention(
                assessment_id=assessments[0].assessment_id,
                message="First",
                created_at_us=102_000_000,
                sent_at_us=106_000_000,
            ),
            models.Intervention(
                assessment_id=assessments[1].assessment_id,
                message="Second",
                created_at_us=105_000_000,
            ),
        ]
    )
    session.commit()

    assert [
        (
            record.case_id,
            record.target_speaker_id,
            record.assessment_id,
            record.status,
            record.created_at,
            record.sent_at,
        )
        for record in list_intervention_records(
            session=session, now=lambda: datetime.fromtimestamp(110, UTC)
        )
    ] == [
        (
            "case",
            "configured-subject",
            assessments[0].assessment_id,
            "sent",
            datetime.fromtimestamp(102, UTC),
            datetime.fromtimestamp(106, UTC),
        ),
        (
            "case",
            "configured-subject",
            assessments[1].assessment_id,
            "pending",
            datetime.fromtimestamp(105, UTC),
            None,
        ),
    ]
