from unittest.mock import Mock

import pytest
from sqlmodel import Session

from normative_conformance.errors import NotFound
from normative_conformance.models.normative_model import NormativeModelVersion
from normative_conformance.services.model.get_model import get_model


def test_decodes_requested_model_version():
    session = Mock(spec=Session)
    session.get.return_value = NormativeModelVersion(
        model_id="rule",
        version="2",
        name="Rule",
        type="undesired",
        repair_allowance_us=10,
        rules_json='[{"rule_id":"one","description":"First","sql":"SELECT 1"}]',
        parameters_json='{"threshold":3}',
    )
    model = get_model(model_id="rule", version="2", session=session)
    session.get.assert_called_once_with(NormativeModelVersion, ("rule", "2"))
    assert model.model_dump() == {
        "model_id": "rule",
        "version": "2",
        "name": "Rule",
        "type": "undesired",
        "repair_allowance_us": 10,
        "rules": [{"rule_id": "one", "description": "First", "sql": "SELECT 1"}],
        "parameters": {"threshold": 3},
    }


def test_missing_version_raises_not_found():
    session = Mock(spec=Session)
    session.get.return_value = None
    with pytest.raises(NotFound, match=r"^The model was not found$"):
        get_model(model_id="missing", version="1", session=session)
