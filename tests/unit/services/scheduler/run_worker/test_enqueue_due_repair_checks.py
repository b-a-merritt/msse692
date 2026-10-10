from datetime import datetime
from datetime import timezone
from importlib import import_module
from unittest.mock import Mock

import pytest

from normative_conformance.errors import EnqueueFailed

module = import_module(
    "normative_conformance.services.scheduler.run_worker.enqueue_due_repair_checks"
)


def test_consumes_due_deadlines_but_preserves_future_work(*, monkeypatch):
    deadlines = {"overdue": 99, "due": 100, "future": 101}
    request = Mock()
    monkeypatch.setattr(module, "request_repair_check", request)
    scheduler = object()
    module.enqueue_due_repair_checks(
        repair_deadlines=deadlines,
        scheduler=scheduler,
        now=lambda: datetime(1970, 1, 1, 0, 0, 0, 100, tzinfo=timezone.utc),
    )
    assert deadlines == {"future": 101}
    assert [call.kwargs for call in request.call_args_list] == [
        {"case_id": "overdue", "scheduler": scheduler},
        {"case_id": "due", "scheduler": scheduler},
    ]


def test_failed_enqueue_preserves_its_deadline_and_stops_processing(*, monkeypatch):
    error = EnqueueFailed(message="Queue unavailable")
    request = Mock(side_effect=error)
    monkeypatch.setattr(module, "request_repair_check", request)
    deadlines = {"first": 99, "second": 100}
    with pytest.raises(EnqueueFailed) as caught:
        module.enqueue_due_repair_checks(
            repair_deadlines=deadlines,
            scheduler=object(),
            now=lambda: datetime(1970, 1, 1, 0, 0, 0, 100, tzinfo=timezone.utc),
        )
    assert caught.value is error
    assert deadlines == {"first": 99, "second": 100}
    assert request.call_count == 1
