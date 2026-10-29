"""The worker reads the most recently stored model."""

from datetime import UTC
from datetime import datetime

from normative_conformance import models
from normative_conformance.schemas.discovery import DiscoveredModel
from normative_conformance.services.model.newest_model import newest_model


def test_no_model_before_discovery(session):
    assert newest_model(session=session) is None


def test_returns_the_newest_model_with_its_topics(session):
    older = models.NormativeModel(discovered_at_us=10)
    newer = models.NormativeModel(discovered_at_us=20)
    session.add_all([older, newer])
    session.flush()
    session.add_all(
        [
            models.NormativeModelTopic(normative_model_id=older.normative_model_id, topic="work"),
            models.NormativeModelTopic(
                normative_model_id=newer.normative_model_id, topic="extended_family"
            ),
            models.NormativeModelTopic(
                normative_model_id=newer.normative_model_id, topic="budgeting"
            ),
        ]
    )
    session.commit()

    assert newest_model(session=session) == DiscoveredModel(
        normative_model_id=newer.normative_model_id,
        discovered_at=datetime(1970, 1, 1, microsecond=20, tzinfo=UTC),
        topics=["budgeting", "extended_family"],
    )
