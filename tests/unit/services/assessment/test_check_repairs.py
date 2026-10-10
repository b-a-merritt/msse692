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
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.model import ModelVersion

module = import_module("normative_conformance.services.assessment.check_repairs")


@pytest.mark.parametrize(
    "new_repair,status,stopped,scheduled",
    [
        (True, "non-conformant", False, True),
        (True, "pending", True, False),
        (False, "non-conformant", False, True),
        (False, "conformant", False, False),
    ],
)
def test_records_repairs_and_resolves_pending_before_requesting_reassessment(
    *, monkeypatch, new_repair, status, stopped, scheduled
):
    session = Mock(spec=Session)
    scheduler = SimpleNamespace(stopped=Event())
    if stopped:
        scheduler.stopped.set()
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
    pending = Assessment(
        assessment_id=1, case_id="case", model_id="harm_phrase", model_version="1", status="pending"
    )
    resolution = Assessment(
        assessment_id=3,
        case_id="case",
        model_id="harm_phrase",
        model_version="1",
        status=status,
        resolves_assessment_id=1,
    )
    repair = Observation(case_id="case", observation_id="apology", sequence=4)
    repair_result = Assessment(
        assessment_id=2, case_id="case", model_id="apology", model_version="1", status="conformant"
    )
    monkeypatch.setattr(module, "write_session", Mock(return_value=nullcontext(session)))
    monkeypatch.setattr(module, "get_case_sequence", Mock(return_value=5))
    monkeypatch.setattr(module, "get_subject_speaker_id", Mock(return_value="subject"))
    monkeypatch.setattr(module, "get_last_repair", Mock(return_value=None))
    find = Mock(return_value=(models[1], repair) if new_repair else None)
    create = Mock(return_value=repair_result)
    resolve = Mock(return_value=resolution)
    pending_rows = Mock(return_value=[pending])
    request = Mock(side_effect=lambda **kwargs: session.commit.assert_called_once())
    for name, value in [
        ("find_repair", find),
        ("create_assessment", create),
        ("resolve_pending", resolve),
        ("list_assessments", pending_rows),
        ("request_assessment", request),
    ]:
        monkeypatch.setattr(module, name, value)

    results = module.check_repairs(
        case_id="case",
        evaluation_id=UUID(int=1),
        engine=object(),
        now=lambda: datetime(1970, 1, 1, 0, 0, 0, 100, tzinfo=timezone.utc),
        scheduler=scheduler,
        models=models,
    )

    assert results == ([repair_result, resolution] if new_repair else [resolution])
    assert find.call_args.kwargs["models"] == [models[1]]
    assert resolve.call_args.kwargs["model"] is models[0]
    assert resolve.call_args.kwargs["snapshot"].through_sequence == 5
    pending_rows.assert_called_once_with(
        case_id="case", status="pending", unresolved=True, session=session
    )
    if new_repair:
        assert create.call_args.kwargs["snapshot"].through_sequence == 4
        assert create.call_args.kwargs["observation_ids"] == ["apology"]
    else:
        create.assert_not_called()
    session.commit.assert_called_once()
    if scheduled:
        request.assert_called_once_with(case_id="case", scheduler=scheduler)
    else:
        request.assert_not_called()


@pytest.mark.parametrize(
    "failure", [SQLAlchemyError("Driver failure"), StorageUnavailable("Stored failure")]
)
def test_storage_failure_never_requests_reassessment(*, monkeypatch, failure):
    monkeypatch.setattr(module, "write_session", Mock(side_effect=failure))
    request = Mock()
    monkeypatch.setattr(module, "request_assessment", request)
    with pytest.raises(StorageUnavailable) as caught:
        module.check_repairs(
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
        assert str(caught.value) == "Repairs could not be checked"
    request.assert_not_called()
