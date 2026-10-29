from datetime import UTC
from datetime import datetime
from unittest.mock import Mock

from sqlmodel import Session

from normative_conformance import models
from normative_conformance.schemas.discovery import DiscoveredModel
from normative_conformance.services.model.store_model import store_model


def test_stores_topics_and_source_assessments_then_commits():
    session = Mock(spec=Session)
    session.flush.side_effect = lambda: setattr(
        session.add.call_args.args[0], "normative_model_id", 7
    )

    result = store_model(
        topics=["budgeting", "extended_family"],
        assessment_ids=[3, 4],
        discovered_at_us=1_000_000,
        session=session,
    )

    assert session.add.call_args.args[0].discovered_at_us == 1_000_000
    assert session.add_all.call_args.args[0] == [
        models.NormativeModelTopic(normative_model_id=7, topic="budgeting"),
        models.NormativeModelTopic(normative_model_id=7, topic="extended_family"),
        models.NormativeModelAssessment(normative_model_id=7, assessment_id=3),
        models.NormativeModelAssessment(normative_model_id=7, assessment_id=4),
    ]
    session.commit.assert_called_once()
    assert result == DiscoveredModel(
        normative_model_id=7,
        discovered_at=datetime(1970, 1, 1, 0, 0, 1, tzinfo=UTC),
        topics=["budgeting", "extended_family"],
    )
