"""A stored model can be read back with its topics and source assessments."""

from sqlmodel import select

from normative_conformance import models
from normative_conformance.services.discovery.store_model import store_model


def test_stores_a_model_with_topics_and_source_assessments(*, session):
    session.add(models.ConversationCase(case_id="case", created_at_us=1))
    session.flush()
    session.add_all(
        [
            models.Observation(
                case_id="case",
                observation_id="chunk",
                sequence=1,
                received_at_us=10,
                speaker_id="A",
                start_at_us=1,
                end_at_us=9,
                transcript="Hello",
                signal_level_min=-30.0,
                signal_level_avg=-20.0,
                signal_level_max=-10.0,
            ),
            models.TargetAssignment(
                case_id="case", target_revision=1, assigned_at_us=1, speaker_id="A"
            ),
        ]
    )
    session.flush()
    assessment = models.Assessment(
        case_id="case",
        target_revision=1,
        model_id="jev-1.14.0",
        prompt_version="conversation-2",
        evaluated_at_us=11,
        completed_at_us=11,
        after_sequence=0,
        through_sequence=1,
        selection_threshold=0.7,
        request_json="{}",
    )
    session.add(assessment)
    session.commit()

    model = store_model(
        topics=["budgeting", "extended_family"],
        assessment_ids=[assessment.assessment_id],
        discovered_at_us=20,
        session=session,
    )

    assert session.exec(
        select(models.NormativeModelTopic.topic).where(
            models.NormativeModelTopic.normative_model_id == model.normative_model_id
        )
    ).all() == ["budgeting", "extended_family"]
    assert session.exec(
        select(models.NormativeModelAssessment.assessment_id).where(
            models.NormativeModelAssessment.normative_model_id == model.normative_model_id
        )
    ).all() == [assessment.assessment_id]
