from unittest.mock import Mock

import pytest

from normative_conformance.errors import NotFound
from normative_conformance.routes import model
from normative_conformance.schemas.model import ModelVersion


def test_listing_wraps_service_results_in_the_list_contract(*, monkeypatch):
    record = ModelVersion(
        model_id="rule",
        name="Rule",
        version="1",
        type="undesired",
        rules=[{"rule_id": "one", "description": "", "sql": "SELECT 1"}],
        parameters={},
    )
    service = Mock(return_value=[record])
    monkeypatch.setattr(model.model, "list_models", service)
    session = object()
    assert model.list_models(session=session).items == [record]
    service.assert_called_once_with(session=session)


def test_version_lookup_forwards_identity_and_propagates_not_found(*, monkeypatch):
    error = NotFound("The model was not found")
    service = Mock(side_effect=error)
    monkeypatch.setattr(model.model, "get_model", service)
    session = object()
    with pytest.raises(NotFound) as caught:
        model.get_model(model_id="requested", version="2", session=session)
    assert caught.value is error
    service.assert_called_once_with(model_id="requested", version="2", session=session)
