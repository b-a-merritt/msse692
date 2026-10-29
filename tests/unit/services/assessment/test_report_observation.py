import pytest

from normative_conformance.services.assessment.report_observation import report_observation


@pytest.mark.parametrize(
    "threshold,topics,primary_topic,behaviors",
    [
        pytest.param(0.7, ["chores", "money"], "chores", ["criticism"], id="at-threshold"),
        pytest.param(0.95, [], "unknown", [], id="above-every-score"),
    ],
)
def test_selects_scores_reaching_the_threshold_in_name_order(
    threshold, topics, primary_topic, behaviors
):
    decision = report_observation(
        observation_id="one",
        observation_ids=["one", "two"],
        topic_scores={"money": 0.9, "chores": 0.7, "work": 0.69},
        primary_topic="chores",
        behavior_scores={"swearing": 0.1, "criticism": 0.7},
        intensity=1.5,
        threshold=threshold,
    )
    assert decision.topics == topics
    assert decision.primary_topic == primary_topic
    assert decision.behaviors == behaviors
    assert decision.topic_scores == {"money": 0.9, "chores": 0.7, "work": 0.69}
    assert decision.behavior_scores == {"swearing": 0.1, "criticism": 0.7}
    assert decision.intensity == 1.5
    assert decision.observation_ids == ["one", "two"]
