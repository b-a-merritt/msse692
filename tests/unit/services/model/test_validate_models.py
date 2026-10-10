from importlib import import_module
from unittest.mock import Mock

import pytest
from sqlmodel import Session

from normative_conformance.errors import InvalidModel
from normative_conformance.errors import StorageUnavailable
from normative_conformance.schemas.model import ModelVersion

module = import_module("normative_conformance.services.model.validate_models")


def test_validates_every_rule_even_when_an_earlier_rule_does_not_match(*, monkeypatch):
    models = [
        ModelVersion(
            model_id=model_id,
            name=model_id,
            version="1",
            type=kind,
            rules=[
                {"rule_id": "first", "description": "", "sql": "SELECT 1"},
                {"rule_id": "second", "description": "", "sql": "SELECT 2"},
            ],
            parameters={"limit": 3},
        )
        for model_id, kind in [("harm_phrase", "undesired"), ("apology", "repairs")]
    ]
    session = Mock(spec=Session)
    monkeypatch.setattr(module, "list_models", Mock(return_value=models))
    evaluate = Mock(return_value=False)
    monkeypatch.setattr(module, "evaluate_model", evaluate)
    assert module.validate_models(session=session) is models
    assert [
        (call.kwargs["model"].model_id, call.kwargs["model"].rules[0].rule_id)
        for call in evaluate.call_args_list
    ] == [
        ("harm_phrase", "first"),
        ("harm_phrase", "second"),
        ("apology", "first"),
        ("apology", "second"),
    ]
    for call in evaluate.call_args_list:
        assert call.kwargs["case_id"] == ""
        assert call.kwargs["through_sequence"] == 0
        assert call.kwargs["model"].parameters == {"limit": 3}
    assert len(models[0].rules) == 2


@pytest.mark.parametrize("kind", ["empty", "repair-only", "unknown-message", "schema", "query"])
def test_invalid_catalog_fails_startup_with_a_stable_reason(*, monkeypatch, kind):
    model = ModelVersion(
        model_id="unlisted" if kind == "unknown-message" else "harm_phrase",
        name="Rule",
        version="1",
        type="repairs" if kind == "repair-only" else "undesired",
        rules=[{"rule_id": "one", "description": "", "sql": "SELECT 1"}],
        parameters={},
    )
    schema_error = ValueError("Invalid field")
    query_error = StorageUnavailable("The model could not be evaluated")
    listing = Mock(
        return_value=[] if kind == "empty" else [model],
        side_effect=schema_error if kind == "schema" else None,
    )
    monkeypatch.setattr(module, "list_models", listing)
    evaluate = Mock(side_effect=query_error if kind == "query" else None)
    monkeypatch.setattr(module, "evaluate_model", evaluate)
    with pytest.raises(InvalidModel) as caught:
        module.validate_models(session=Mock(spec=Session))
    assert (
        str(caught.value)
        == {
            "empty": "No undesired model is available to assess",
            "repair-only": "No undesired model is available to assess",
            "unknown-message": "An undesired model has no intervention message",
            "schema": "A stored model does not match the model schema",
            "query": "A stored model rule could not be evaluated",
        }[kind]
    )
    if kind == "schema":
        assert caught.value.__cause__ is schema_error
    elif kind == "query":
        assert caught.value.__cause__ is query_error
    else:
        evaluate.assert_not_called()
