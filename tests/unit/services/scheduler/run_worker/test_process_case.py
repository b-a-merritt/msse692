from contextlib import nullcontext
from datetime import datetime
from datetime import timezone
from importlib import import_module
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from normative_conformance.models.assessment import Assessment
from normative_conformance.models.case import CaseLog

module = import_module("normative_conformance.services.scheduler.run_worker.process_case")


@pytest.mark.parametrize(
    "repair_status,resolves",
    [
        (None, None),
        ("pending", None),
        ("non-conformant", 1),
        ("conformant", None),
        ("conformant", 1),
    ],
)
def test_commits_progress_and_results_together(monkeypatch, repair_status, resolves):
    case = CaseLog(case_id="case", created_at_us=0, target_speaker_id="A", target_revision=3)
    session = Mock(spec=Session)
    session.get.return_value = case
    monkeypatch.setattr(module, "write_session", Mock(return_value=nullcontext(session)))
    monkeypatch.setattr(module, "get_case_sequence", Mock(return_value=7))
    evaluate = Mock(return_value=[])

    def repair(**kwargs):
        return (
            []
            if repair_status is None
            else [
                Assessment(
                    case_id="case",
                    model_id="repair",
                    model_version="1",
                    status=repair_status,
                    evaluation_id=kwargs["snapshot"].evaluation_id,
                    evaluated_at_us=100,
                    resolves_assessment_id=resolves,
                )
            ]
        )

    monkeypatch.setattr(module, "evaluate_case", evaluate)
    monkeypatch.setattr(module, "check_repairs", repair)
    clock = Mock(return_value=datetime(1970, 1, 1, microsecond=100, tzinfo=timezone.utc))

    def commit():
        assert case.last_handled_sequence == 7
        assert case.last_handled_target_revision == 3

    session.commit.side_effect = commit
    opened = module.process_case(case_id="case", engine=object(), now=clock, models=[])
    assert opened == (100 if repair_status == "conformant" and resolves else None)
    assert evaluate.call_count == (
        2
        if repair_status == "non-conformant" or (repair_status == "conformant" and resolves is None)
        else 1
    )
    session.commit.assert_called_once()
    clock.assert_called_once()
    snapshots = [call.kwargs["snapshot"] for call in evaluate.call_args_list]
    assert {(row.through_sequence, row.evaluated_at_us) for row in snapshots} == {(7, 100)}
    assert all(call.kwargs["subject_speaker_id"] == "A" for call in evaluate.call_args_list)
    assert len({row.evaluation_id for row in snapshots}) == len(snapshots)


@pytest.mark.parametrize("case", [None, CaseLog(case_id="case", created_at_us=0)])
def test_unresolved_or_missing_case_does_not_advance(monkeypatch, case):
    session = Mock(spec=Session)
    session.get.return_value = case
    monkeypatch.setattr(module, "write_session", Mock(return_value=nullcontext(session)))
    evaluate = Mock()
    monkeypatch.setattr(module, "evaluate_case", evaluate)
    assert module.process_case(case_id="case", engine=object(), now=Mock(), models=[]) is None
    evaluate.assert_not_called()
    session.commit.assert_not_called()


def test_assessment_failure_leaves_progress_unhandled(monkeypatch):
    case = CaseLog(case_id="case", created_at_us=0, target_speaker_id="A", target_revision=1)
    session = Mock(spec=Session)
    session.get.return_value = case
    monkeypatch.setattr(module, "write_session", Mock(return_value=nullcontext(session)))
    monkeypatch.setattr(module, "get_case_sequence", Mock(return_value=7))
    monkeypatch.setattr(module, "evaluate_case", Mock(side_effect=SQLAlchemyError("failed")))
    with pytest.raises(SQLAlchemyError):
        module.process_case(
            case_id="case",
            engine=object(),
            models=[],
            now=lambda: datetime(1970, 1, 1, tzinfo=timezone.utc),
        )
    assert case.last_handled_sequence == 0
    assert case.last_handled_target_revision == 0
    session.commit.assert_not_called()
