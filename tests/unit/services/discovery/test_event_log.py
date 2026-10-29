from normative_conformance.services.discovery.event_log import event_log


def test_keeps_each_trace_and_its_event_order():
    log = event_log(traces=[["chores", "budgeting"], ["work"]])
    assert [[event["concept:name"] for event in trace] for trace in log] == [
        ["chores", "budgeting"],
        ["work"],
    ]
