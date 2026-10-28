from sqlmodel import select

from normative_conformance import models
from normative_conformance.schemas.decision import DecisionAnswers
from normative_conformance.schemas.decision import ObservationAnswers
from normative_conformance.services.intervention.create_intervention import MESSAGES
from normative_conformance.services.intervention.create_intervention import create_intervention


def test_intervene_assessment_stores_an_eligible_pending_intervention(*, session):
    session.add(models.ConversationCase(case_id="case", created_at_us=0))
    session.flush()
    session.add_all(
        [
            models.Observation(
                case_id="case",
                observation_id="one",
                sequence=1,
                received_at_us=0,
                start_at_us=0,
                end_at_us=1,
                speaker_id="A",
                transcript="You never listen",
                signal_level_min=-40,
                signal_level_avg=-30,
                signal_level_max=-20,
            ),
            models.TargetAssignment(
                case_id="case", target_revision=1, assigned_at_us=0, speaker_id="A"
            ),
        ]
    )
    session.flush()
    assessment = models.Assessment(
        case_id="case",
        target_revision=1,
        model_id="jev-1.14.0",
        prompt_version="conversation-1",
        evaluated_at_us=0,
        completed_at_us=5,
        after_sequence=0,
        through_sequence=1,
        action="intervene",
        action_confidence=0.9,
        selection_threshold=0.7,
        request_json="{}",
    )
    session.add(assessment)
    session.flush()

    create_intervention(
        assessment=assessment,
        answers=DecisionAnswers(
            model="jev-1.14.0",
            prompt_version="conversation-1",
            observations=[
                ObservationAnswers(
                    observation_id="one",
                    topic_scores={},
                    primary_topic="unknown",
                    behavior_scores={"criticism": 0.9},
                    intensity=1.5,
                )
            ],
            action="intervene",
            action_probabilities={"intervene": 1.0},
            action_confidence=0.9,
        ),
        session=session,
    )
    session.commit()

    [stored] = session.exec(select(models.Intervention)).all()
    assert (stored.assessment_id, stored.created_at_us, stored.sent_at_us) == (
        assessment.assessment_id,
        5,
        None,
    )
    assert stored.message == MESSAGES["criticism"]
