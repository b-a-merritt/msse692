import pytest

from normative_conformance.services.discovery.matches_rules import matches_rules


@pytest.mark.parametrize(
    "trace,expected",
    [
        pytest.param(["chores", "extended_family"], False, id="budgeting-missing"),
        pytest.param(["chores", "extended_family", "budgeting"], True, id="all-required"),
        pytest.param(["budgeting", "chores", "extended_family"], True, id="either-order"),
        pytest.param(["chores", "budgeting"], False, id="extended-family-missing"),
    ],
)
def test_matches_only_when_every_required_topic_has_come_up(trace, expected):
    assert matches_rules(trace=trace, required_topics=["budgeting", "extended_family"]) is expected


def test_no_rules_never_match():
    assert matches_rules(trace=["chores"], required_topics=[]) is False


def test_an_ended_trace_never_matches():
    assert (
        matches_rules(
            trace=["extended_family", "budgeting", "undesired_behavior"],
            required_topics=["budgeting", "extended_family"],
        )
        is False
    )
