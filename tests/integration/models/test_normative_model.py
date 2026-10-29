"""Discovered models reference real assessments and are append-only."""

import pytest
from sqlalchemy import delete
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from normative_conformance import models


def test_source_assessments_must_exist(*, session):
    model = models.NormativeModel(discovered_at_us=20)
    session.add(model)
    session.flush()
    session.add(
        models.NormativeModelAssessment(
            normative_model_id=model.normative_model_id, assessment_id=99
        )
    )
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        session.commit()


@pytest.mark.parametrize(
    "statement",
    [
        pytest.param(update(models.NormativeModel).values(discovered_at_us=21), id="model-update"),
        pytest.param(delete(models.NormativeModel), id="model-delete"),
        pytest.param(update(models.NormativeModelTopic).values(topic="chores"), id="topic-update"),
        pytest.param(delete(models.NormativeModelTopic), id="topic-delete"),
    ],
)
def test_models_are_append_only(*, session, statement):
    model = models.NormativeModel(discovered_at_us=20)
    session.add(model)
    session.flush()
    session.add(
        models.NormativeModelTopic(normative_model_id=model.normative_model_id, topic="work")
    )
    session.commit()

    with pytest.raises(IntegrityError, match="append-only"):
        session.execute(statement)
