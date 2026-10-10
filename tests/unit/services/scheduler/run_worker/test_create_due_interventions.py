from contextlib import nullcontext
from datetime import datetime
from datetime import timezone
from importlib import import_module
from unittest.mock import Mock

from sqlmodel import Session

module = import_module(
    "normative_conformance.services.scheduler.run_worker.create_due_interventions"
)


def test_due_windows_are_consumed_once_and_one_failure_does_not_block_other_cases(*, monkeypatch):
    windows = {"failing": 80, "due": 90, "future": 91}
    session = Mock(spec=Session)
    monkeypatch.setattr(
        module, "write_session", Mock(side_effect=lambda **kwargs: nullcontext(session))
    )

    def create(*, case_id, **kwargs):
        assert case_id not in windows
        if case_id == "failing":
            raise RuntimeError("Decision failed")

    create_mock = Mock(side_effect=create)
    monkeypatch.setattr(module.intervention, "create_intervention", create_mock)

    def clock():
        return datetime(1970, 1, 1, 0, 0, 0, 100, tzinfo=timezone.utc)

    for _ in range(2):
        module.create_due_interventions(
            intervention_windows=windows, intervention_window_us=10, engine=object(), now=clock
        )
    assert windows == {"future": 91}
    assert [call.kwargs for call in create_mock.call_args_list] == [
        {"case_id": "failing", "since_us": 80, "session": session, "now": clock},
        {"case_id": "due", "since_us": 90, "session": session, "now": clock},
    ]
