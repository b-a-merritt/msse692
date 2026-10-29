from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance import models
from normative_conformance.schemas.discovery import DiscoveredModel
from normative_conformance.timestamps import from_microseconds


def newest_model(*, session: Session) -> DiscoveredModel | None:
    """Return the most recently stored model, or None before any discovery."""
    model = session.exec(
        select(models.NormativeModel).order_by(col(models.NormativeModel.normative_model_id).desc())
    ).first()

    if model is None:
        return None

    topics = session.exec(
        select(models.NormativeModelTopic.topic)
        .where(models.NormativeModelTopic.normative_model_id == model.normative_model_id)
        .order_by(col(models.NormativeModelTopic.topic))
    ).all()

    assert model.normative_model_id is not None

    return DiscoveredModel(
        normative_model_id=model.normative_model_id,
        discovered_at=from_microseconds(value=model.discovered_at_us),
        topics=list(topics),
    )
