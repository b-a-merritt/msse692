from normative_conformance.models.assessment import Assessment


def should_open_intervention_window(
    *,
    assessments: list[Assessment],
    evaluation_id: str,
    resolutions_only: bool,
) -> bool:
    """Check for a new undesired confirmation without changing assessments or windows.

    Repair checks pass `resolutions_only`: a new repair is conformant but is not a confirmation.
    """
    return any(
        assessment.status == "conformant"
        and assessment.evaluation_id == evaluation_id
        and (not resolutions_only or assessment.resolves_assessment_id is not None)
        for assessment in assessments
    )
