from normative_conformance.schemas.assessment import ObservationDecision

# Stored with each assessment, so earlier assessments keep the threshold they were made under.
SELECTION_THRESHOLD = 0.7


def report_observation(
    *,
    observation_id: str,
    topic_scores: dict[str, float],
    primary_topic: str,
    behavior_scores: dict[str, float],
    intensity: float | None,
    threshold: float,
) -> ObservationDecision:
    """Select topics and behaviors whose scores reach the threshold, in name order."""
    topics = _selected(scores=topic_scores, threshold=threshold)
    return ObservationDecision(
        observation_id=observation_id,
        topic_scores=topic_scores,
        topics=topics,
        # A primary topic is only reported when its own score selects it.
        primary_topic=primary_topic if primary_topic in topics else "unknown",
        behavior_scores=behavior_scores,
        behaviors=_selected(scores=behavior_scores, threshold=threshold),
        intensity=intensity,
    )


def _selected(*, scores: dict[str, float], threshold: float) -> list[str]:
    return sorted(name for name, score in scores.items() if score >= threshold)
