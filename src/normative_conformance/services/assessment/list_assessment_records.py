from typing import cast

from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance import models
from normative_conformance.schemas.assessment import Assessment
from normative_conformance.schemas.assessment import ObservationDecision
from normative_conformance.schemas.decision import Action
from normative_conformance.services.assessment.report_observation import report_observation
from normative_conformance.timestamps import from_microseconds


def list_assessment_records(*, case_id: str, session: Session) -> list[Assessment]:
    """Read the retained decisions and classifications, in assessment ID order."""
    assessments = session.exec(
        select(models.Assessment, models.TargetAssignment.speaker_id)
        .join(models.TargetAssignment)
        .where(models.Assessment.case_id == case_id)
        .order_by(col(models.Assessment.assessment_id))
    ).all()
    thresholds = {
        assessment.assessment_id: assessment.selection_threshold for assessment, _ in assessments
    }
    assessment_ids = list(thresholds)
    probabilities: dict[int, dict[str, float]] = {}
    for action in session.exec(
        select(models.AssessmentActionProbability).where(
            col(models.AssessmentActionProbability.assessment_id).in_(assessment_ids)
        )
    ):
        probabilities.setdefault(action.assessment_id, {})[action.action] = action.probability
    classifications = session.exec(
        select(models.Classification, models.Observation.observation_id)
        .join(models.Observation)
        .where(col(models.Classification.assessment_id).in_(assessment_ids))
        .order_by(col(models.Observation.observation_id))
    ).all()
    classification_ids = [row.classification_id for row, _ in classifications]
    topic_scores: dict[int, dict[str, float]] = {}
    for topic in session.exec(
        select(models.ClassificationTopicScore).where(
            col(models.ClassificationTopicScore.classification_id).in_(classification_ids)
        )
    ):
        topic_scores.setdefault(topic.classification_id, {})[topic.topic] = topic.score
    behavior_scores: dict[int, dict[str, float]] = {}
    for behavior in session.exec(
        select(models.ClassificationBehaviorScore).where(
            col(models.ClassificationBehaviorScore.classification_id).in_(classification_ids)
        )
    ):
        behavior_scores.setdefault(behavior.classification_id, {})[behavior.behavior] = (
            behavior.score
        )
    decisions: dict[int, list[ObservationDecision]] = {}
    for classification, observation_id in classifications:
        assert classification.classification_id is not None
        decisions.setdefault(classification.assessment_id, []).append(
            report_observation(
                observation_id=observation_id,
                topic_scores=topic_scores.get(classification.classification_id, {}),
                primary_topic=classification.primary_topic,
                behavior_scores=behavior_scores.get(classification.classification_id, {}),
                intensity=classification.intensity,
                threshold=thresholds[classification.assessment_id],
            )
        )
    records = []
    for assessment, speaker_id in assessments:
        assert assessment.assessment_id is not None and speaker_id is not None
        records.append(
            Assessment(
                assessment_id=assessment.assessment_id,
                case_id=assessment.case_id,
                subject_speaker_id=speaker_id,
                target_revision=assessment.target_revision,
                model=assessment.model_id,
                prompt_version=assessment.prompt_version,
                evaluated_at=from_microseconds(value=assessment.evaluated_at_us),
                completed_at=from_microseconds(value=assessment.completed_at_us),
                after_sequence=assessment.after_sequence,
                through_sequence=assessment.through_sequence,
                selection_threshold=assessment.selection_threshold,
                observations=decisions.get(assessment.assessment_id, []),
                action=cast(Action, assessment.action),
                action_confidence=assessment.action_confidence,
                action_probabilities=probabilities.get(assessment.assessment_id, {}),
            )
        )
    return records
