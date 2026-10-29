from datetime import UTC
from datetime import datetime

from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.services.decision.turns import turns


def test_groups_consecutive_speech_from_one_speaker_in_time_order():
    first = ObservationInput(
        case_id="case",
        observation_id="first",
        speaker_id="A",
        start_at="1970-01-01T00:00:00Z",
        end_at="1970-01-01T00:00:01Z",
        transcript="Hello",
        signal_level_min=-40,
        signal_level_avg=-30,
        signal_level_max=-20,
    )
    second = first.model_copy(
        update={
            "observation_id": "second",
            "start_at": datetime(1970, 1, 1, second=1, tzinfo=UTC),
            "end_at": datetime(1970, 1, 1, second=2, tzinfo=UTC),
        }
    )
    reply = first.model_copy(
        update={
            "observation_id": "reply",
            "speaker_id": "B",
            "start_at": datetime(1970, 1, 1, second=2, tzinfo=UTC),
            "end_at": datetime(1970, 1, 1, second=3, tzinfo=UTC),
        }
    )
    again = first.model_copy(
        update={
            "observation_id": "again",
            "start_at": datetime(1970, 1, 1, second=3, tzinfo=UTC),
            "end_at": datetime(1970, 1, 1, second=4, tzinfo=UTC),
        }
    )
    # Arrival order differs from time order.
    assert turns(observations=[again, reply, second, first]) == [
        [first, second],
        [reply],
        [again],
    ]


def test_equal_times_are_ordered_by_observation_id():
    later = ObservationInput(
        case_id="case",
        observation_id="b",
        speaker_id="A",
        start_at="1970-01-01T00:00:00Z",
        end_at="1970-01-01T00:00:01Z",
        transcript="Hello",
        signal_level_min=-40,
        signal_level_avg=-30,
        signal_level_max=-20,
    )
    earlier = later.model_copy(update={"observation_id": "a"})
    assert turns(observations=[later, earlier]) == [[earlier, later]]


def test_no_speech_has_no_turns():
    assert turns(observations=[]) == []
