from sqlmodel import Session

from conversation_monitor.models.assessment import Assessment
from conversation_monitor.models.assessment import AssessmentActionProbability
from conversation_monitor.models.assessment import Classification
from conversation_monitor.models.assessment import ClassificationBehaviorScore
from conversation_monitor.models.assessment import ClassificationTopicScore
from conversation_monitor.schemas.decision import DecisionAnswers
from conversation_monitor.schemas.decision import DecisionSnapshot
from conversation_monitor.schemas.decision import ObservationAnswers
from conversation_monitor.services.assessment.report_observation import SELECTION_THRESHOLD
from conversation_monitor.timestamps import to_microseconds


def store_assessment(
    *,
    session: Session,
    snapshot: DecisionSnapshot,
    answers: DecisionAnswers,
    request_json: str,
    observation_keys: dict[str, int],
    completed_at_us: int,
) -> int:
    """Add the assessment and its answers without committing, and return its ID."""
    assessment = _assessment(
        snapshot=snapshot,
        answers=answers,
        request_json=request_json,
        completed_at_us=completed_at_us,
    )
    session.add(assessment)
    session.flush()
    assert assessment.assessment_id is not None

    session.add_all(
        [
            AssessmentActionProbability(
                assessment_id=assessment.assessment_id, action=action, probability=probability
            )
            for action, probability in answers.action_probabilities.items()
        ]
    )
    classifications = [
        Classification(
            assessment_id=assessment.assessment_id,
            observation_key=observation_keys[row.observation_id],
            primary_topic=row.primary_topic,
            intensity=row.intensity,
        )
        for row in answers.observations
    ]
    session.add_all(classifications)

    # The scores reference classification IDs, which the database assigns.
    session.flush()
    session.add_all(
        [
            score
            for classification, row in zip(classifications, answers.observations, strict=True)
            for score in _scores(classification=classification, answers=row)
        ]
    )

    return assessment.assessment_id


def _assessment(
    *,
    snapshot: DecisionSnapshot,
    answers: DecisionAnswers,
    request_json: str,
    completed_at_us: int,
) -> Assessment:
    return Assessment(
        case_id=snapshot.case_id,
        target_revision=snapshot.target_revision,
        model_id=answers.model,
        prompt_version=answers.prompt_version,
        evaluated_at_us=to_microseconds(value=snapshot.captured_at),
        completed_at_us=completed_at_us,
        after_sequence=snapshot.after_sequence,
        through_sequence=snapshot.through_sequence,
        action=answers.action,
        action_confidence=answers.action_confidence,
        selection_threshold=SELECTION_THRESHOLD,
        request_json=request_json,
    )


def _scores(
    *,
    classification: Classification,
    answers: ObservationAnswers,
) -> list[ClassificationTopicScore | ClassificationBehaviorScore]:
    classification_id = classification.classification_id
    assert classification_id is not None
    return [
        *(
            ClassificationTopicScore(classification_id=classification_id, topic=topic, score=score)
            for topic, score in answers.topic_scores.items()
        ),
        *(
            ClassificationBehaviorScore(
                classification_id=classification_id, behavior=behavior, score=score
            )
            for behavior, score in answers.behavior_scores.items()
        ),
    ]
