from sqlmodel import Session

from normative_conformance.models.assessment import Assessment
from normative_conformance.models.assessment import AssessmentActionProbability
from normative_conformance.models.assessment import Classification
from normative_conformance.models.assessment import ClassificationBehaviorScore
from normative_conformance.models.assessment import ClassificationTopicScore
from normative_conformance.schemas.decision import DecisionAnswers
from normative_conformance.schemas.decision import DecisionSnapshot
from normative_conformance.services.assessment.report_observation import SELECTION_THRESHOLD
from normative_conformance.timestamps import to_microseconds


def store_assessment(
    *,
    session: Session,
    snapshot: DecisionSnapshot,
    answers: DecisionAnswers,
    request_json: str,
    observation_keys: dict[str, int],
    completed_at_us: int,
) -> Assessment:
    """Store the batch decision and its classifications in the caller's transaction."""
    assessment = Assessment(
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
    for classification, row in zip(classifications, answers.observations, strict=True):
        assert classification.classification_id is not None
        session.add_all(
            [
                ClassificationTopicScore(
                    classification_id=classification.classification_id, topic=topic, score=score
                )
                for topic, score in row.topic_scores.items()
            ]
        )
        session.add_all(
            [
                ClassificationBehaviorScore(
                    classification_id=classification.classification_id,
                    behavior=behavior,
                    score=score,
                )
                for behavior, score in row.behavior_scores.items()
            ]
        )
    return assessment
