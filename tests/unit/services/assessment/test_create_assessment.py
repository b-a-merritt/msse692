from datetime import datetime
from datetime import timezone
from unittest.mock import Mock

import pytest
from sqlmodel import Session

from normative_conformance.schemas.assessment import CaseSnapshot
from normative_conformance.schemas.assessment import Explanation
from normative_conformance.schemas.model import ModelVersion
from normative_conformance.services.assessment.create_assessment import create_assessment


@pytest.mark.parametrize(
    "status,deadline,evidence,reason,outcome",
    [
        ("pending", 110, ["first"], "awaiting_repair", "pending"),
        ("conformant", None, None, "matched", "satisfied"),
        ("non-conformant", None, ["repair"], "repaired", "not_satisfied"),
    ],
)
def test_builds_explanations_for_each_rule_without_committing(
    *, status, deadline, evidence, reason, outcome
):
    model = ModelVersion(
        model_id="rule",
        name="Rule",
        version="2",
        type="undesired",
        rules=[{"rule_id": rule, "description": "", "sql": "SELECT 1"} for rule in ["one", "two"]],
        parameters={},
    )
    snapshot = CaseSnapshot(
        case_id="case", evaluation_id="evaluation", through_sequence=3, evaluated_at_us=100
    )
    session = Mock(spec=Session)
    result = create_assessment(
        model=model,
        snapshot=snapshot,
        status=status,
        session=session,
        next_due_at_us=deadline,
        resolves_assessment_id=7,
        observation_ids=evidence,
    )
    assert (result.case_id, result.model_id, result.model_version, result.evaluation_id) == (
        "case",
        "rule",
        "2",
        "evaluation",
    )
    assert result.through_sequence == 3
    assert result.evaluated_at_us == 100
    assert result.resolves_assessment_id == 7
    assert result.next_due_at_us == deadline
    explanation = Explanation.model_validate_json(result.explanation_json)
    assert explanation.reason_code == reason
    assert [rule.rule_id for rule in explanation.rules] == ["one", "two"]
    for rule in explanation.rules:
        assert rule.outcome == outcome
        assert rule.observation_ids == (evidence or [])
        assert rule.deadline_at == (
            datetime(1970, 1, 1, 0, 0, 0, 110, tzinfo=timezone.utc) if deadline else None
        )
    session.add.assert_called_once_with(result)
    session.flush.assert_called_once()
    session.commit.assert_not_called()
