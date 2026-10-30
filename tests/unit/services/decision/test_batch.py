from datetime import UTC
from datetime import datetime

import pytest

from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.services.decision.batch import batch_end
from normative_conformance.services.observation.load_case_speech import IngestedObservation


def _ingested(*, sequence, speaker_id, start_second, end_second):
    """Speech is received as it ends."""
    return IngestedObservation(
        observation_key=sequence,
        sequence=sequence,
        received_at=datetime.fromtimestamp(end_second, UTC),
        observation=ObservationInput(
            case_id="case",
            observation_id=str(sequence),
            speaker_id=speaker_id,
            start_at=datetime.fromtimestamp(start_second, UTC),
            end_at=datetime.fromtimestamp(end_second, UTC),
            transcript="Hello",
            signal_level_min=-40,
            signal_level_avg=-30,
            signal_level_max=-20,
        ),
    )


@pytest.mark.parametrize(
    "after_sequence,expected",
    [
        pytest.param(0, 3, id="other-speech-joins-the-target-turn-that-follows"),
        pytest.param(3, 6, id="next-target-turn"),
        pytest.param(6, None, id="target-turn-still-open"),
    ],
)
def test_batch_ends_when_the_target_stops_speaking(after_sequence, expected):
    ingested = [
        _ingested(sequence=1, speaker_id="B", start_second=0, end_second=5),
        _ingested(sequence=2, speaker_id="A", start_second=5, end_second=10),
        _ingested(sequence=3, speaker_id="A", start_second=10, end_second=15),
        _ingested(sequence=4, speaker_id="B", start_second=15, end_second=20),
        _ingested(sequence=5, speaker_id="PENDING", start_second=20, end_second=25),
        _ingested(sequence=6, speaker_id="A", start_second=25, end_second=30),
        _ingested(sequence=7, speaker_id="B", start_second=30, end_second=35),
        _ingested(sequence=8, speaker_id="A", start_second=35, end_second=40),
    ]
    assert (
        batch_end(
            ingested=ingested,
            target_speaker_id="A",
            after_sequence=after_sequence,
            max_seconds=60,
            max_turns=3,
            idle_seconds=20,
            now=datetime.fromtimestamp(41, UTC),
        )
        == expected
    )


@pytest.mark.parametrize(
    "max_seconds,expected",
    [
        pytest.param(20, 2, id="speech-reaches-the-limit"),
        pytest.param(21, None, id="speech-below-the-limit"),
    ],
)
def test_batch_ends_once_its_speech_spans_the_limit(max_seconds, expected):
    ingested = [
        _ingested(sequence=1, speaker_id="A", start_second=0, end_second=10),
        _ingested(sequence=2, speaker_id="A", start_second=12, end_second=20),
        _ingested(sequence=3, speaker_id="A", start_second=20, end_second=20.5),
    ]
    assert (
        batch_end(
            ingested=ingested,
            target_speaker_id="A",
            after_sequence=0,
            max_seconds=max_seconds,
            max_turns=3,
            idle_seconds=20,
            now=datetime.fromtimestamp(22, UTC),
        )
        == expected
    )


@pytest.mark.parametrize(
    "now_second,expected",
    [
        pytest.param(30, 2, id="idle"),
        pytest.param(29, None, id="speech-may-continue"),
    ],
)
def test_batch_ends_when_no_speech_has_arrived_for_the_idle_time(now_second, expected):
    ingested = [
        _ingested(sequence=1, speaker_id="B", start_second=0, end_second=5),
        _ingested(sequence=2, speaker_id="B", start_second=5, end_second=10),
    ]
    assert (
        batch_end(
            ingested=ingested,
            target_speaker_id="A",
            after_sequence=0,
            max_seconds=60,
            max_turns=3,
            idle_seconds=20,
            now=datetime.fromtimestamp(now_second, UTC),
        )
        == expected
    )


def test_nothing_new_has_no_batch():
    ingested = [_ingested(sequence=1, speaker_id="A", start_second=0, end_second=5)]
    assert (
        batch_end(
            ingested=ingested,
            target_speaker_id="A",
            after_sequence=1,
            max_seconds=60,
            max_turns=3,
            idle_seconds=20,
            now=datetime.fromtimestamp(100, UTC),
        )
        is None
    )


@pytest.mark.parametrize(
    "target_speaker_id,expected",
    [
        pytest.param("Z", 3, id="other-speakers-reach-the-limit"),
        pytest.param("B", 2, id="target-turn-ends-first"),
    ],
)
def test_batch_ends_after_the_turn_limit(target_speaker_id, expected):
    ingested = [
        _ingested(sequence=1, speaker_id="A", start_second=0, end_second=1),
        _ingested(sequence=2, speaker_id="B", start_second=1, end_second=2),
        _ingested(sequence=3, speaker_id="C", start_second=2, end_second=3),
        _ingested(sequence=4, speaker_id="D", start_second=3, end_second=4),
    ]
    assert (
        batch_end(
            ingested=ingested,
            target_speaker_id=target_speaker_id,
            after_sequence=0,
            max_seconds=60,
            max_turns=3,
            idle_seconds=20,
            now=datetime.fromtimestamp(5, UTC),
        )
        == expected
    )
