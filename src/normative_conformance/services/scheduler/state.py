from dataclasses import dataclass
from dataclasses import field
from threading import Event


@dataclass(kw_only=True)
class SchedulerState:
    stopped: Event = field(default_factory=Event, init=False)
