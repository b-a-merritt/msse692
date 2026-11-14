from pm4py.objects.log.obj import Event
from pm4py.objects.log.obj import EventLog
from pm4py.objects.log.obj import Trace


def event_log(*, traces: list[list[str]]) -> EventLog:
    return EventLog(
        [Trace([Event({"concept:name": activity}) for activity in events]) for events in traces],
    )
