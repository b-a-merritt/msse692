from datetime import datetime
from datetime import timezone
from importlib import import_module
from unittest.mock import Mock
from uuid import UUID

import pytest
from sqlmodel import Session

from normative_conformance.models.assessment import Assessment
from normative_conformance.schemas.model import ModelVersion

module = import_module("normative_conformance.services.assessment.evaluate_case")


@pytest.mark.parametrize("status,resolves", [("pending", None), (None, None), ("conformant", 7)])
def test_evaluates_only_undesired_models_without_committing(*, monkeypatch, status, resolves):
    session = Mock(spec=Session)
    evaluation_id = UUID(int=1)
    result = (
        None
        if status is None
        else Assessment(
            subject_speaker_id="subject",
            assessment_id=8,
            case_id="case",
            evaluation_id=str(evaluation_id),
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
    monkeypatch.setattr(module, "get_case_sequence", Mock(return_value=3))
    last = Mock(return_value=None)
    subject = Mock(return_value="subject")
    assess = Mock(return_value=result)
    monkeypatch.setattr(module, "get_last_repair", last)
    monkeypatch.setattr(module, "get_subject_speaker_id", subject)
    monkeypatch.setattr(module, "assess_model", assess)
    clock = Mock(return_value=datetime(1970, 1, 1, 0, 0, 0, 100, tzinfo=timezone.utc))

    results = module.evaluate_case(
        case_id="case",
        evaluation_id=evaluation_id,
        session=session,
        now=clock,
        models=models,
    )

    assert results == ([] if result is None else [result])
    session.commit.assert_not_called()
    clock.assert_called_once()
    last.assert_called_once_with(case_id="case", session=session)
    assess.assert_called_once()
    assert assess.call_args.kwargs["model"] is models[0]
    assert assess.call_args.kwargs["snapshot"].evaluated_at_us == 100
    assert assess.call_args.kwargs["snapshot"].through_sequence == 3
    subject.assert_called_once_with(case_id="case", session=session)


def test_unresolved_target_waits_without_assessing(monkeypatch):
    session = Mock(spec=Session)
    monkeypatch.setattr(module, "get_subject_speaker_id", Mock(return_value=None))
    sequence = Mock()
    monkeypatch.setattr(module, "get_case_sequence", sequence)
    assert (
        module.evaluate_case(
            case_id="case",
            evaluation_id=UUID(int=1),
            session=session,
            now=Mock(),
            models=[],
        )
        == []
    )
    sequence.assert_not_called()
    session.commit.assert_not_called()
