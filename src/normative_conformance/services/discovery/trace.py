from normative_conformance.schemas.assessment import Assessment

UNDESIRED_BEHAVIOR = "undesired_behavior"

# Swearing alone is not undesired; swearing at the listener also scores as criticism or contempt.
_UNDESIRED_BEHAVIORS = frozenset(
    {
        "criticism",
        "contempt",
        "cruelty",
        "defensiveness",
        "stonewalling",
        "interruption",
    }
)


def trace(
    *,
    assessments: list[Assessment],
    target_revision: int,
) -> list[str]:
    events: list[str] = []
    for assessment in sorted(assessments, key=lambda row: row.assessment_id):
        if assessment.target_revision != target_revision:
            continue
        # Only target turns are asked about behaviors.
        if any(_UNDESIRED_BEHAVIORS & set(turn.behaviors) for turn in assessment.observations):
            return [*events, UNDESIRED_BEHAVIOR]
        for turn in assessment.observations:
            events.extend(topic for topic in turn.topics if topic not in events)
    return events
