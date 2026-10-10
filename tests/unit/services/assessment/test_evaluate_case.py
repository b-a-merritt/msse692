from contextlib import nullcontext
from datetime import datetime
from datetime import timezone
from importlib import import_module
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from normative_conformance.errors import StorageUnavailable
from normative_conformance.models.assessment import Assessment
from normative_conformance.schemas.model import ModelVersion

module = import_module("normative_conformance.services.assessment.evaluate_case")


@pytest.mark.parametrize(
    "replayed,status,resolves,stopped,scheduled",
    [
        (False, "pending", None, False, True),
        (False, None, None, False, False),
        (True, "conformant", 7, False, True),
        (True, "conformant", None, False, False),
        (True, "pending", None, True, False),
    ],
)
def test_replays_saved_results_or_evaluates_only_undesired_models_then_schedules(
    *, monkeypatch, replayed, status, resolves, stopped, scheduled
):
    session = Mock(spec=Session)
    engine = object()
    scheduler = SimpleNamespace(stopped=Event())
    if stopped:
        scheduler.stopped.set()
    evaluation_id = UUID(int=1)
    result = (
        None
        if status is None
        else Assessment(
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
    monkeypatch.setattr(module, "write_session", Mock(return_value=nullcontext(session)))
    monkeypatch.setattr(module, "get_case_sequence", Mock(return_value=3))
    monkeypatch.setattr(module, "list_assessments", Mock(return_value=[result] if replayed else []))
    last = Mock(return_value=None)
    subject = Mock(return_value="subject")
    assess = Mock(return_value=result)
    request = Mock(side_effect=lambda **kwargs: session.commit.assert_called_once())
    monkeypatch.setattr(module, "get_last_repair", last)
    monkeypatch.setattr(module, "get_subject_speaker_id", subject)
    monkeypatch.setattr(module, "assess_model", assess)
    monkeypatch.setattr(module, "request_repair_check", request)
    clock = Mock(return_value=datetime(1970, 1, 1, 0, 0, 0, 100, tzinfo=timezone.utc))

    results = module.evaluate_case(
        case_id="case",
        evaluation_id=evaluation_id,
        engine=engine,
        now=clock,
        scheduler=scheduler,
        models=models,
    )

    assert results == ([] if result is None else [result])
    session.commit.assert_called_once()
    clock.assert_called_once()
    if replayed:
        assess.assert_not_called()
        last.assert_not_called()
        subject.assert_not_called()
    else:
        assess.assert_called_once()
        assert assess.call_args.kwargs["model"] is models[0]
        assert assess.call_args.kwargs["snapshot"].evaluated_at_us == 100
        assert assess.call_args.kwargs["snapshot"].through_sequence == 3
        subject.assert_called_once_with(session=session)
    if scheduled:
        request.assert_called_once_with(case_id="case", scheduler=scheduler)
    else:
        request.assert_not_called()


@pytest.mark.parametrize(
    "failure", [SQLAlchemyError("Driver failure"), StorageUnavailable("Stored failure")]
)
def test_storage_failure_preserves_cause_and_never_schedules(*, monkeypatch, failure):
    monkeypatch.setattr(module, "write_session", Mock(side_effect=failure))
    request = Mock()
    monkeypatch.setattr(module, "request_repair_check", request)
    with pytest.raises(StorageUnavailable) as caught:
        module.evaluate_case(
            case_id="case",
            evaluation_id=UUID(int=1),
            engine=object(),
            now=Mock(),
            scheduler=Mock(),
            models=[],
        )
    if isinstance(failure, StorageUnavailable):
        assert caught.value is failure
    else:
        assert caught.value.__cause__ is failure
        assert str(caught.value) == "The case could not be assessed"
    request.assert_not_called()
