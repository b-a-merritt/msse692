import pm4py

from normative_conformance.services.discovery.event_log import event_log
from normative_conformance.services.discovery.trace import UNDESIRED_BEHAVIOR

# Fewer conversations would make every topic of one conversation a rule.
MIN_TRACES = 3


def discover_rules(*, traces: list[list[str]]) -> list[str] | None:
    """Find the topics that came before undesired behavior in every trace that ended in it"""
    ended = [events for events in traces if events[-1:] == [UNDESIRED_BEHAVIOR]]

    if len(ended) < MIN_TRACES:
        return None

    model = pm4py.discover_declare(
        event_log(traces=ended),
        allowed_templates={"precedence"},
        min_support_ratio=1.0,
        min_confidence_ratio=1.0,
    )

    return sorted(
        topic for topic, target in model.get("precedence", {}) if target == UNDESIRED_BEHAVIOR
    )
