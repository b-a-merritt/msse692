from importlib import import_module
from unittest.mock import Mock

import pytest
from sqlmodel import Session

from normative_conformance.models.assessment import Assessment
from normative_conformance.schemas.assessment import CaseSnapshot
from normative_conformance.schemas.model import ModelVersion

module = import_module("normative_conformance.services.assessment.assess_model")


@pytest.mark.parametrize(
    "previous_status,resolves,matches,allowance,expected_status,reused",
    [
        ("pending", None, [], 10, "pending", True),
        (None, None, [False], 10, None, False),
        (None, None, [True], 10, "pending", False),
        (None, None, [True], None, "conformant", False),
        ("conformant", None, [True, True], 10, "conformant", True),
        ("conformant", 4, [True, True], 10, "conformant", True),
        ("conformant", 4, [True, False], 10, "pending", False),
        ("non-conformant", None, [True], 10, "pending", False),
    ],
)
def test_reuses_active_occurrences_or_creates_a_new_detection(
    *, monkeypatch, previous_status, resolves, matches, allowance, expected_status, reused
):
    model = ModelVersion(
        model_id="harm_phrase",
        name="Threat",
        version="2",
        type="undesired",
        repair_allowance_us=allowance,
        rules=[{"rule_id": "one", "description": "", "sql": "SELECT 1"}],
        parameters={},
    )
    snapshot = CaseSnapshot(
        case_id="case", evaluation_id="new", through_sequence=9, evaluated_at_us=100
    )
    previous = (
        None
        if previous_status is None
        else Assessment(
            assessment_id=5,
            case_id="case",
            evaluation_id="previous",
            model_id="harm_phrase",
            model_version="2",
            through_sequence=7,
            evaluated_at_us=80,
            status=previous_status,
            next_due_at_us=90 if previous_status == "pending" else None,
            resolves_assessment_id=resolves,
            explanation_json="{}",
        )
    )
    session = Mock(spec=Session)
    pending_result = Mock()
    pending_result.first.return_value = previous if previous_status == "pending" else None
    latest_result = Mock()
    latest_result.first.return_value = previous
    session.exec.side_effect = [pending_result, latest_result]
    original = Assessment(
        assessment_id=4,
        case_id="case",
        evaluation_id="original",
        through_sequence=2,
        status="pending",
    )
    session.get.return_value = original
    evaluate = Mock(side_effect=matches)
    monkeypatch.setattr(module, "evaluate_model", evaluate)

    result = module.assess_model(
        model=model,
        snapshot=snapshot,
        subject_speaker_id="subject",
        last_repair=None,
        session=session,
    )

    assert evaluate.call_count == len(matches)
    if reused:
        assert result is previous
        session.add.assert_not_called()
    elif expected_status is None:
        assert result is None
        session.add.assert_not_called()
    else:
        assert result.status == expected_status
        assert result.next_due_at_us == (110 if allowance is not None else None)
        assert result.evaluation_id == "new"
        assert result.through_sequence == 9
        session.add.assert_called_once_with(result)
        session.flush.assert_called_once()
    if len(matches) == 2:
        assert evaluate.call_args.kwargs["through_sequence"] == (2 if resolves else 7)
    if resolves is not None and matches and matches[0]:
        session.get.assert_called_once_with(Assessment, 4)
    session.commit.assert_not_called()
    query = session.exec.call_args_list[0].args[0].compile()
    assert query.params["case_id_1"] == "case"
    assert query.params["model_id_1"] == "harm_phrase"
    assert query.params["model_version_1"] == "2"
    assert "NOT IN" in str(query)
