from sqlmodel import Session

from normative_conformance.models.intervention import Intervention
from normative_conformance.schemas.decision import DecisionAnswers
from normative_conformance.services.assessment.report_observation import SELECTION_THRESHOLD

# Fixed prompts by target behavior; transcript text never reaches them.
MESSAGES = {
    "interruption": "You cut them off. Let them finish before you respond.",
    "swearing": "You used strong language. Try saying what you need instead.",
    "criticism": "You described the person, not the issue. Try naming what they did.",
    "cruelty": "That could be heard as meant to hurt. Take a moment before you continue.",
    "contempt": "That could come across as mocking. Try responding to what they said.",
    "defensiveness": "You may be defending more than listening. Try acknowledging their point.",
    "stonewalling": "You may be shutting the conversation down. Try saying what you need.",
}
GENERAL_MESSAGE = "The conversation may be getting tense. Take a moment before you continue."


def create_intervention(
    *, assessment_id: int, created_at_us: int, answers: DecisionAnswers, session: Session
) -> Intervention | None:
    """Add a prompt for an `intervene` recommendation, worded for its strongest target behavior.

    `created_at_us` is when the assessment completed.
    """
    if answers.action != "intervene":
        return None
    intervention = Intervention(
        assessment_id=assessment_id,
        message=_message(answers),
        created_at_us=created_at_us,
    )
    session.add(intervention)
    return intervention


def _message(answers: DecisionAnswers) -> str:
    """Behavior scores exist only for target speech; below the threshold none is named."""
    score, behavior = max(
        (
            (score, behavior)
            for row in answers.observations
            for behavior, score in row.behavior_scores.items()
        ),
        default=(0.0, ""),
    )
    return MESSAGES[behavior] if score >= SELECTION_THRESHOLD else GENERAL_MESSAGE
