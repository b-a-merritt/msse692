import pm4py

from normative_conformance.services.discovery.event_log import event_log
from normative_conformance.services.discovery.trace import UNDESIRED_BEHAVIOR


def matches_rules(*, trace: list[str], required_topics: list[str]) -> bool:
    """Whether every required topic has come up in a trace that has not ended"""
    if not required_topics or trace[-1:] == [UNDESIRED_BEHAVIOR]:
        return False

    model: dict[str, dict[tuple[str, str], dict[str, int]]] = {
        "precedence": {(topic, UNDESIRED_BEHAVIOR): {} for topic in required_topics}
    }
    result = pm4py.conformance_declare(
        event_log(traces=[[*trace, UNDESIRED_BEHAVIOR]]),
        model,
    )

    return bool(result[0]["is_fit"])
