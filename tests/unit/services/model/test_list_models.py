from unittest.mock import Mock

from sqlmodel import Session

from normative_conformance.models.normative_model import NormativeModelVersion
from normative_conformance.services.model.list_models import list_models


def test_decodes_stored_catalog_without_committing():
    session = Mock(spec=Session)
    session.exec.return_value.all.return_value = [
        NormativeModelVersion(
            model_id="apology",
            name="Apology",
            version="2",
            type="repairs",
            rules_json='[{"rule_id":"one","description":"","sql":"SELECT 1"}]',
            parameters_json='{"phrases":["sorry"]}',
        )
    ]
    results = list_models(session=session)
    assert results[0].parameters == {"phrases": ["sorry"]}
    assert results[0].rules[0].sql == "SELECT 1"
    assert results[0].type == "repairs"
    assert results[0].version == "2"
    session.commit.assert_not_called()
