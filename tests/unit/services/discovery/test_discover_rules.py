from normative_conformance.services.discovery.discover_rules import discover_rules


def test_requires_topics_that_came_before_every_undesired_behavior():
    traces = [
        ["chores", "extended_family", "budgeting", "undesired_behavior"],
        ["budgeting", "work", "extended_family", "undesired_behavior"],
        ["extended_family", "budgeting", "undesired_behavior"],
        # Calm conversations do not remove a rule, even when they share a topic.
        ["budgeting", "chores"],
        ["extended_family"],
    ]
    assert discover_rules(traces=traces) == ["budgeting", "extended_family"]


def test_no_shared_topic_gives_no_rules():
    traces = [
        ["chores", "undesired_behavior"],
        ["work", "undesired_behavior"],
        ["budgeting", "undesired_behavior"],
    ]
    assert discover_rules(traces=traces) == []


def test_fewer_than_three_ended_traces_give_no_model():
    traces = [
        ["extended_family", "budgeting", "undesired_behavior"],
        ["extended_family", "budgeting", "undesired_behavior"],
        ["extended_family", "budgeting"],
    ]
    assert discover_rules(traces=traces) is None
