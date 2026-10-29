"""Discovered models survive storage, reference real assessments, and are append-only."""

import pytest
from sqlalchemy import delete
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from normative_conformance import models


def test_model_with_topics_and_source_assessments_round_trips(*, session):
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
    model = models.NormativeModel(discovered_at_us=20)
    session.add_all([assessment, model])
    session.flush()
    session.add_all(
        [
            models.NormativeModelTopic(normative_model_id=model.normative_model_id, topic=topic)
            for topic in ["budgeting", "extended_family"]
        ]
        + [
            models.NormativeModelAssessment(
                normative_model_id=model.normative_model_id,
                assessment_id=assessment.assessment_id,
            )
        ]
    )
    session.commit()
    session.expunge_all()

    assert session.get(models.NormativeModel, model.normative_model_id).discovered_at_us == 20
    assert session.exec(select(models.NormativeModelTopic.topic)).all() == [
        "budgeting",
        "extended_family",
    ]
    assert session.exec(select(models.NormativeModelAssessment.assessment_id)).all() == [
        assessment.assessment_id
    ]


def test_source_assessments_must_exist(*, session):
    model = models.NormativeModel(discovered_at_us=20)
    session.add(model)
    session.flush()
    session.add(
        models.NormativeModelAssessment(
            normative_model_id=model.normative_model_id, assessment_id=99
        )
    )
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        session.commit()


@pytest.mark.parametrize(
    "statement",
    [
        pytest.param(update(models.NormativeModel).values(discovered_at_us=21), id="model-update"),
        pytest.param(delete(models.NormativeModel), id="model-delete"),
        pytest.param(update(models.NormativeModelTopic).values(topic="chores"), id="topic-update"),
        pytest.param(delete(models.NormativeModelTopic), id="topic-delete"),
    ],
)
def test_models_are_append_only(*, session, statement):
    model = models.NormativeModel(discovered_at_us=20)
    session.add(model)
    session.flush()
    session.add(
        models.NormativeModelTopic(normative_model_id=model.normative_model_id, topic="work")
    )
    session.commit()

    with pytest.raises(IntegrityError, match="append-only"):
        session.execute(statement)
