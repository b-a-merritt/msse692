from importlib import import_module
from unittest.mock import Mock

import pytest
from sqlmodel import Session

from normative_conformance.models.assessment import Assessment
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.assessment import CaseSnapshot
from normative_conformance.schemas.model import ModelVersion

module = import_module("normative_conformance.services.assessment.check_repairs")


@pytest.mark.parametrize(
    "new_repair,status",
    [
        (True, "non-conformant"),
        (True, "pending"),
        (False, "non-conformant"),
        (False, "conformant"),
    ],
)
def test_records_repairs_and_resolves_pending_without_committing(
    *, monkeypatch, new_repair, status
):
    session = Mock(spec=Session)
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
        subject_speaker_id="subject",
        assessment_id=1,
        case_id="case",
        model_id="harm_phrase",
        model_version="1",
        status="pending",
    )
    resolution = Assessment(
        subject_speaker_id="subject",
        assessment_id=3,
        case_id="case",
        model_id="harm_phrase",
        model_version="1",
        status=status,
        resolves_assessment_id=1,
    )
    repair = Observation(case_id="case", observation_id="apology", sequence=4)
    repair_result = Assessment(
        subject_speaker_id="subject",
        assessment_id=2,
        case_id="case",
        model_id="apology",
        model_version="1",
        status="conformant",
    )
    monkeypatch.setattr(module, "get_last_repair", Mock(return_value=None))
    find = Mock(return_value=(models[1], repair) if new_repair else None)
    create = Mock(return_value=repair_result)
    resolve = Mock(return_value=resolution)
    pending_rows = Mock(return_value=[pending])
    for name, value in [
        ("find_repair", find),
        ("create_assessment", create),
        ("resolve_pending", resolve),
        ("list_assessments", pending_rows),
    ]:
        monkeypatch.setattr(module, name, value)

    results = module.check_repairs(
        snapshot=CaseSnapshot(
            case_id="case", evaluation_id="evaluation", through_sequence=5, evaluated_at_us=100
        ),
        subject_speaker_id="subject",
        session=session,
        models=models,
    )

    assert results == ([repair_result, resolution] if new_repair else [resolution])
    assert find.call_args.kwargs["models"] == [models[1]]
    assert resolve.call_args.kwargs["model"] is models[0]
    assert resolve.call_args.kwargs["snapshot"].through_sequence == 5
    pending_rows.assert_called_once_with(
        case_id="case", status="pending", unresolved=True, current_target=True, session=session
    )
    if new_repair:
        assert create.call_args.kwargs["snapshot"].through_sequence == 4
        assert create.call_args.kwargs["observation_ids"] == ["apology"]
    else:
        create.assert_not_called()
    session.commit.assert_not_called()
