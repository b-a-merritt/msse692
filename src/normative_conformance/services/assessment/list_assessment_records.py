from itertools import groupby
from operator import itemgetter
from typing import cast

from sqlalchemy.orm import Mapped
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
    probabilities = _scores(
        session=session,
        owner=col(models.AssessmentActionProbability.assessment_id),
        name=col(models.AssessmentActionProbability.action),
        value=col(models.AssessmentActionProbability.probability),
        owner_ids=list(thresholds),
    )
    decisions = _decisions(session=session, thresholds=thresholds)

    return [
        _record(
            assessment=assessment,
            speaker_id=speaker_id,
            decisions=decisions,
            probabilities=probabilities,
        )
        for assessment, speaker_id in assessments
    ]


def _record(
    *,
    assessment: models.Assessment,
    speaker_id: str | None,
    decisions: dict[int, list[ObservationDecision]],
    probabilities: dict[int, dict[str, float]],
) -> Assessment:
    assert assessment.assessment_id is not None and speaker_id is not None
    return Assessment(
        assessment_id=assessment.assessment_id,
        case_id=assessment.case_id,
        target_speaker_id=speaker_id,
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


def _decisions(
    *,
    session: Session,
    thresholds: dict[int | None, float],
) -> dict[int, list[ObservationDecision]]:
    """Report each assessment's classifications under the threshold it was made with."""
    classifications = session.exec(
        select(models.Classification, models.Observation.observation_id)
        .join(models.Observation)
        .where(col(models.Classification.assessment_id).in_(list(thresholds)))
        # Classifications are stored in the order their snapshot listed the speech.
        .order_by(
            col(models.Classification.assessment_id), col(models.Classification.classification_id)
        )
    ).all()

    classification_ids = [row.classification_id for row, _ in classifications]
    topic_scores = _scores(
        session=session,
        owner=col(models.ClassificationTopicScore.classification_id),
        name=col(models.ClassificationTopicScore.topic),
        value=col(models.ClassificationTopicScore.score),
        owner_ids=classification_ids,
    )
    behavior_scores = _scores(
        session=session,
        owner=col(models.ClassificationBehaviorScore.classification_id),
        name=col(models.ClassificationBehaviorScore.behavior),
        value=col(models.ClassificationBehaviorScore.score),
        owner_ids=classification_ids,
    )

    return {
        assessment_id: [
            _decision(
                classification=classification,
                observation_id=observation_id,
                topic_scores=topic_scores,
                behavior_scores=behavior_scores,
                threshold=thresholds[assessment_id],
            )
            for classification, observation_id in rows
        ]
        for assessment_id, rows in groupby(classifications, key=lambda row: row[0].assessment_id)
    }


def _decision(
    *,
    classification: models.Classification,
    observation_id: str,
    topic_scores: dict[int, dict[str, float]],
    behavior_scores: dict[int, dict[str, float]],
    threshold: float,
) -> ObservationDecision:
    assert classification.classification_id is not None
    return report_observation(
        observation_id=observation_id,
        topic_scores=topic_scores.get(classification.classification_id, {}),
        primary_topic=classification.primary_topic,
        behavior_scores=behavior_scores.get(classification.classification_id, {}),
        intensity=classification.intensity,
        threshold=threshold,
    )


def _scores(
    *,
    session: Session,
    owner: Mapped[int],
    name: Mapped[str],
    value: Mapped[float],
    owner_ids: list[int | None],
) -> dict[int, dict[str, float]]:
    # Grouping relies on the rows arriving sorted by owner.
    rows = session.exec(select(owner, name, value).where(owner.in_(owner_ids)).order_by(owner))
    return {
        owner_id: {key: score for _, key, score in group}
        for owner_id, group in groupby(rows, key=itemgetter(0))
    }
