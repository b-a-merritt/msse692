from sqlmodel import Session

from conversation_monitor.schemas.decision import PatternEvidence
from conversation_monitor.services.assessment.list_assessment_records import list_assessment_records
from conversation_monitor.services.discovery.matches_rules import matches_rules
from conversation_monitor.services.discovery.trace import trace
from conversation_monitor.services.model.newest_model import newest_model


def find_evidence(
    *, case_id: str, target_revision: int, session: Session
) -> PatternEvidence | None:
    """Check the case's earlier classifications against the newest model."""
    model = newest_model(session=session)

    # A model without topics never matches.
    if model is None or not model.topics:
        return None

    # The batch about to be assessed is not stored yet, so only earlier batches count.
    events = trace(
        assessments=list_assessment_records(
            case_id=case_id,
            session=session,
        ),
        target_revision=target_revision,
    ).events

    if not matches_rules(
        trace=events,
        required_topics=model.topics,
    ):
        return None

    return PatternEvidence(
        normative_model_id=model.normative_model_id,
        topics=model.topics,
    )
