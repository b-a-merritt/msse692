from _thread import LockType
from dataclasses import dataclass
from dataclasses import field
from threading import Event
from threading import Lock

from persistqueue import SQLiteAckQueue
from persistqueue.sqlackqueue import AckStatus


def _case_ids(*, waiting: list[dict[str, str]], kind: str) -> set[str]:
    return {item["case_id"] for item in waiting if item["kind"] == kind}


@dataclass(kw_only=True)
class SchedulerState:
    queue: SQLiteAckQueue
    lock: LockType = field(default_factory=Lock, init=False)
    stopped: Event = field(default_factory=Event, init=False)
    queued_cases: set[str] = field(default_factory=set, init=False)
    queued_repairs: set[str] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        """Include requests left waiting by a previous process."""
        waiting = [
            item["data"]
            for item in self.queue.queue()
            if item["status"] in (int(AckStatus.inited), int(AckStatus.ready))
        ]
        self.queued_cases = _case_ids(waiting=waiting, kind="assess_case")
        self.queued_repairs = _case_ids(waiting=waiting, kind="check_repairs")
