from datetime import datetime
from datetime import timezone
from importlib import import_module
from unittest.mock import Mock
from uuid import UUID

import pytest
from persistqueue import SQLiteAckQueue

from normative_conformance.models.assessment import Assessment
from normative_conformance.services.scheduler.state import SchedulerState

module = import_module(
    "normative_conformance.services.scheduler.run_worker.process_assessment_task"
)


@pytest.mark.parametrize("kind", ["assess_case", "check_repairs"])
@pytest.mark.parametrize("opened", [None, 80])
def test_releases_waiting_membership_before_evaluation_and_preserves_existing_window(
    *, monkeypatch, kind, opened
):
    queue = Mock(spec=SQLiteAckQueue)
    queue.queue.return_value = []
    scheduler = SchedulerState(queue=queue)
    waiting = scheduler.queued_cases if kind == "assess_case" else scheduler.queued_repairs
    waiting.add("case")
    task = {"kind": kind, "case_id": "case", "evaluation_id": str(UUID(int=1))}
    deadlines = {"case": 10, "other": 20}
    windows = {} if opened is None else {"case": opened}
    rows = [
        Assessment(
            case_id="case",
            evaluation_id=task["evaluation_id"],
            status="conformant",
            evaluated_at_us=100,
            resolves_assessment_id=7 if kind == "check_repairs" else None,
            next_due_at_us=150,
        )
    ]

    def evaluate(**kwargs):
        assert "case" not in waiting
        assert not scheduler.lock.locked()
        waiting.add("case")
        return rows

    evaluate_mock = Mock(side_effect=evaluate)
    monkeypatch.setattr(
        module.assessment,
        "evaluate_case" if kind == "assess_case" else "check_repairs",
        evaluate_mock,
    )
    engine = object()

    def clock():
        return datetime(1970, 1, 1, 0, 0, 0, 100, tzinfo=timezone.utc)

    module.process_assessment_task(
        task=task,
        scheduler=scheduler,
        engine=engine,
        now=clock,
        repair_deadlines=deadlines,
        intervention_windows=windows,
        models=[],
    )

    assert waiting == {"case"}
    assert deadlines == {"case": 150, "other": 20}
    assert windows == {"case": 100 if opened is None else opened}
    evaluate_mock.assert_called_once_with(
        case_id="case",
        evaluation_id=UUID(int=1),
        scheduler=scheduler,
        engine=engine,
        now=clock,
        models=[],
    )


def test_no_results_clear_only_the_current_cases_deadline(*, monkeypatch):
    queue = Mock(spec=SQLiteAckQueue)
    queue.queue.return_value = []
    scheduler = SchedulerState(queue=queue)
    monkeypatch.setattr(module.assessment, "evaluate_case", Mock(return_value=[]))
    deadlines = {"case": 10, "other": 20}
    windows = {}
    module.process_assessment_task(
        task={"kind": "assess_case", "case_id": "case", "evaluation_id": str(UUID(int=1))},
        scheduler=scheduler,
        engine=object(),
        now=lambda: datetime(1970, 1, 1, tzinfo=timezone.utc),
        repair_deadlines=deadlines,
        intervention_windows=windows,
        models=[],
    )
    assert deadlines == {"other": 20}
    assert windows == {}


def test_unknown_kind_fails_before_clock_or_evaluation():
    clock = Mock()
    with pytest.raises(ValueError, match=r"^Unknown assessment task kind$"):
        module.process_assessment_task(
            task={"kind": "unknown"},
            scheduler=object(),
            engine=object(),
            now=clock,
            repair_deadlines={},
            intervention_windows={},
            models=[],
        )
    clock.assert_not_called()
