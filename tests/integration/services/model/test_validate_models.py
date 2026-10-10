import json

import pytest
from pydantic import ValidationError
from sqlalchemy import text

from normative_conformance import models
from normative_conformance.errors import InvalidModel
from normative_conformance.errors import StorageUnavailable
from normative_conformance.services.model.list_models import list_models
from normative_conformance.services.model.validate_models import validate_models

from ...storage import persist


def test_seeded_catalog_is_valid(*, session):
    assert validate_models(session=session) == list_models(session=session)


def test_schema_defect_is_invalid(*, session):
    persist(
        session=session,
        record=models.NormativeModelVersion(
            model_id="harm_phrase",
            name="Test model",
            version="2",
            rules_json=json.dumps([]),
            parameters_json="{}",
        ),
    )

    with pytest.raises(
        InvalidModel, match="A stored model does not match the model schema"
    ) as caught:
        validate_models(session=session)

    assert isinstance(caught.value.__cause__, ValidationError)


@pytest.mark.parametrize(
    "sql",
    [
        "SELEC 1",
        "SELECT 1 FROM missing_table",
        "SELECT missing_function(1)",
        "SELECT 1 WHERE :missing_parameter IS NULL",
    ],
)
def test_rule_that_cannot_run_is_invalid(*, session, sql):
    persist(
        session=session,
        record=models.NormativeModelVersion(
            model_id="harm_phrase",
            name="Test model",
            version="2",
            rules_json=json.dumps([{"rule_id": "rule", "description": "", "sql": sql}]),
            parameters_json="{}",
        ),
    )

    with pytest.raises(InvalidModel, match="A stored model rule could not be evaluated") as caught:
        validate_models(session=session)

    assert isinstance(caught.value.__cause__, StorageUnavailable)


def test_every_rule_is_checked_after_one_finds_no_match(*, session):
    persist(
        session=session,
        record=models.NormativeModelVersion(
            model_id="harm_phrase",
            name="Test model",
            version="2",
            rules_json=json.dumps(
                [
                    {"rule_id": "first", "description": "", "sql": "SELECT 1 WHERE 0"},
                    {"rule_id": "second", "description": "", "sql": "SELEC 1"},
                ]
            ),
            parameters_json="{}",
        ),
    )

    with pytest.raises(InvalidModel, match="A stored model rule could not be evaluated"):
        validate_models(session=session)


def test_undesired_model_without_intervention_message_is_invalid(*, session):
    persist(
        session=session,
        record=models.NormativeModelVersion(
            model_id="unmessaged",
            name="Test model",
            version="2",
            rules_json=json.dumps(
                [{"rule_id": "rule", "description": "", "sql": "SELECT 1 WHERE :case_id IS NULL"}]
            ),
            parameters_json="{}",
        ),
    )

    with pytest.raises(InvalidModel, match="An undesired model has no intervention message"):
        validate_models(session=session)


def test_catalog_without_undesired_model_is_invalid(*, session):
    session.exec(text("DROP TRIGGER model_no_delete"))
    session.exec(text("DELETE FROM normative_model_version WHERE type = 'undesired'"))
    session.commit()

    with pytest.raises(InvalidModel, match="No undesired model is available to assess"):
        validate_models(session=session)
