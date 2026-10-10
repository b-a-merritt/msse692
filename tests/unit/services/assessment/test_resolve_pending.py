from importlib import import_module
from unittest.mock import Mock

import pytest
from sqlmodel import Session

from normative_conformance.models.assessment import Assessment
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.assessment import CaseSnapshot
from normative_conformance.schemas.assessment import Explanation
from normative_conformance.schemas.model import ModelVersion

module = import_module("normative_conformance.services.assessment.resolve_pending")


@pytest.mark.parametrize(
    "at,has_repair,still_matches,expected",
    [
        (109, False, False, "pending"),
        (110, False, False, "conformant"),
        (111, False, False, "conformant"),
        (109, True, True, "pending"),
        (111, True, True, "conformant"),
        (109, True, False, "non-conformant"),
        (111, True, False, "non-conformant"),
    ],
)
def test_resolution_uses_original_evidence_and_deadline(
    *, monkeypatch, at, has_repair, still_matches, expected
):
    model = ModelVersion(
        model_id="harm_phrase",
        name="Threat",
        version="1",
        type="undesired",
        rules=[{"rule_id": "one", "description": "", "sql": "SELECT 1"}],
        parameters={},
    )
    repair_model = ModelVersion(
        model_id="apology",
        name="Apology",
        version="1",
        type="repairs",
        rules=[{"rule_id": "repair", "description": "", "sql": "SELECT 1"}],
        parameters={},
    )
    pending = Assessment(
        assessment_id=7,
        case_id="case",
        evaluation_id="original",
        model_id="harm_phrase",
        model_version="1",
        through_sequence=2,
        evaluated_at_us=100,
        status="pending",
        next_due_at_us=110,
        explanation_json="{}",
    )
    observation = Observation(
        case_id="case", observation_id="apology", sequence=4, start_at_us=10, end_at_us=20
    )
    find = Mock(return_value=(repair_model, observation) if has_repair else None)
    evaluate = Mock(return_value=still_matches)
    monkeypatch.setattr(module, "find_repair", find)
    monkeypatch.setattr(module, "evaluate_model", evaluate)
    session = Mock(spec=Session)
    snapshot = CaseSnapshot(
        case_id="case", evaluation_id="check", through_sequence=5, evaluated_at_us=at
    )

    result = module.resolve_pending(
        pending=pending,
        model=model,
        repair_models=[repair_model],
        snapshot=snapshot,
        subject_speaker_id="subject",
        session=session,
    )

    assert result.status == expected
    assert pending.status == "pending"
    assert pending.next_due_at_us == 110
    assert find.call_args.kwargs["deadline_at_us"] == 110
    if has_repair:
        assert evaluate.call_args.kwargs["through_sequence"] == 2
        assert evaluate.call_args.kwargs["after_observation"] is observation
    else:
        evaluate.assert_not_called()
    if expected == "pending":
        assert result is pending
        session.add.assert_not_called()
    else:
        assert result.resolves_assessment_id == 7
        assert result.through_sequence == 5
        assert result.next_due_at_us is None
        explanation = Explanation.model_validate_json(result.explanation_json)
        assert explanation.rules[0].observation_ids == (
            ["apology"] if expected == "non-conformant" else []
        )
        session.add.assert_called_once_with(result)
    session.commit.assert_not_called()
