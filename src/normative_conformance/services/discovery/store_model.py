from sqlmodel import Session

from normative_conformance import models
from normative_conformance.schemas.discovery import DiscoveredModel
from normative_conformance.timestamps import from_microseconds


def store_model(
    *,
    topics: list[str],
    assessment_ids: list[int],
    discovered_at_us: int,
    session: Session,
) -> DiscoveredModel:
    """Store a new model with its required topics and source assessments, then commit."""
    model = models.NormativeModel(discovered_at_us=discovered_at_us)
    session.add(model)
    session.flush()
    assert model.normative_model_id is not None
    session.add_all(
        [
            models.NormativeModelTopic(normative_model_id=model.normative_model_id, topic=topic)
            for topic in topics
        ]
        + [
            models.NormativeModelAssessment(
                normative_model_id=model.normative_model_id, assessment_id=assessment_id
            )
            for assessment_id in assessment_ids
        ]
    )
    session.commit()
    return DiscoveredModel(
        normative_model_id=model.normative_model_id,
        discovered_at=from_microseconds(value=discovered_at_us),
        topics=topics,
    )
