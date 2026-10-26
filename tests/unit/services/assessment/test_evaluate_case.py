from importlib import import_module
from unittest.mock import Mock

import pytest
from sqlmodel import Session

from normative_conformance.models.assessment import Assessment
from normative_conformance.schemas.assessment import CaseSnapshot
from normative_conformance.schemas.model import ModelVersion

module = import_module("normative_conformance.services.assessment.evaluate_case")


@pytest.mark.parametrize("status,resolves", [("pending", None), (None, None), ("conformant", 7)])
def test_evaluates_only_undesired_models_without_committing(*, monkeypatch, status, resolves):
    session = Mock(spec=Session)
    result = (
        None
        if status is None
        else Assessment(
            subject_speaker_id="subject",
            assessment_id=8,
            case_id="case",
            evaluation_id="evaluation",
            model_id="harm_phrase",
            model_version="1",
            through_sequence=3,
            evaluated_at_us=100,
            status=status,
            resolves_assessment_id=resolves,
            next_due_at_us=110 if status == "pending" else None,
        )
    )
    models = [
        ModelVersion(
            model_id=name,
            name=name,
            version="1",
            type=kind,
            rules=[{"rule_id": "one", "description": "", "sql": "SELECT 1"}],
            parameters={},
        )
        for name, kind in [("harm_phrase", "undesired"), ("apology", "repairs")]
    ]
    last = Mock(return_value=None)
    assess = Mock(return_value=result)
    monkeypatch.setattr(module, "get_last_repair", last)
    monkeypatch.setattr(module, "assess_model", assess)
    snapshot = CaseSnapshot(
        case_id="case", evaluation_id="evaluation", through_sequence=3, evaluated_at_us=100
    )

    results = module.evaluate_case(
        snapshot=snapshot,
        subject_speaker_id="subject",
        session=session,
        models=models,
    )

    assert results == ([] if result is None else [result])
    session.commit.assert_not_called()
    last.assert_called_once_with(case_id="case", session=session)
    assess.assert_called_once()
    assert assess.call_args.kwargs["model"] is models[0]
    assert assess.call_args.kwargs["snapshot"] is snapshot
    assert assess.call_args.kwargs["subject_speaker_id"] == "subject"
