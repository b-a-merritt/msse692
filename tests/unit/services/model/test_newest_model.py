from datetime import UTC
from datetime import datetime
from unittest.mock import Mock

from sqlmodel import Session

from normative_conformance import models
from normative_conformance.schemas.discovery import DiscoveredModel
from normative_conformance.services.model.newest_model import newest_model


def test_no_model_before_discovery():
    session = Mock(spec=Session)
    session.exec.return_value.first.return_value = None

    assert newest_model(session=session) is None


def test_reports_the_model_with_its_topics():
    session = Mock(spec=Session)
    session.exec.return_value.first.return_value = models.NormativeModel(
        normative_model_id=4, discovered_at_us=20
    )
    session.exec.return_value.all.return_value = ["budgeting", "extended_family"]

    assert newest_model(session=session) == DiscoveredModel(
        normative_model_id=4,
        discovered_at=datetime(1970, 1, 1, microsecond=20, tzinfo=UTC),
        topics=["budgeting", "extended_family"],
    )
