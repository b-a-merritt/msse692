from datetime import datetime
from datetime import timezone
from importlib import import_module
from unittest.mock import Mock
from uuid import UUID

from sqlmodel import Session

from normative_conformance.models.assessment import Assessment
from normative_conformance.models.observation import Observation

module = import_module("normative_conformance.services.assessment.list_assessment_records")


def test_preserves_each_records_evidence_prefix_and_resolution_link(*, monkeypatch):
    session = Mock(spec=Session)
    explanation = (
        '{"reason_code":"matched","summary":"Match","rules":['
        '{"rule_id":"one","outcome":"satisfied","reason":"Match",'
        '"observation_ids":[],"deadline_at":null}]}'
    )
    rows = [
        Assessment(
            assessment_id=identity,
            case_id="case",
            evaluation_id=str(UUID(int=identity)),
            model_id="rule",
            model_version="1",
            through_sequence=prefix,
            evaluated_at_us=100,
            status=status,
            next_due_at_us=deadline,
            resolves_assessment_id=resolves,
            explanation_json=explanation,
        )
        for identity, prefix, status, deadline, resolves in [
            (1, 1, "pending", 110, None),
            (2, 2, "conformant", None, 1),
        ]
    ]
    observations = [
        Observation(case_id="case", observation_id=name, sequence=sequence)
        for sequence, name in [(1, "first"), (2, "second"), (3, "later")]
    ]
    monkeypatch.setattr(module, "list_assessments", Mock(return_value=rows))
    monkeypatch.setattr(module, "get_subject_speaker_id", Mock(return_value="subject"))
    history = Mock(return_value=observations)
    monkeypatch.setattr(module, "get_case_history", history)
    results = module.list_assessment_records(case_id="case", session=session)
    assert [row.extent.observation_ids for row in results] == [["first"], ["first", "second"]]
    assert [row.extent.observation_count for row in results] == [1, 2]
    assert [row.resolves_assessment_id for row in results] == [None, 1]
    assert [row.next_due_at for row in results] == [
        datetime(1970, 1, 1, 0, 0, 0, 110, tzinfo=timezone.utc),
        None,
    ]
    assert results[0].explanation.reason_code == "matched"
    history.assert_called_once_with(case_id="case", through_sequence=2, session=session)


def test_empty_case_does_not_require_experiment_configuration(*, monkeypatch):
    monkeypatch.setattr(module, "list_assessments", Mock(return_value=[]))
    subject = Mock()
    monkeypatch.setattr(module, "get_subject_speaker_id", subject)
    assert module.list_assessment_records(case_id="case", session=Mock(spec=Session)) == []
    subject.assert_not_called()
