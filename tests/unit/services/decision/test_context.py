from datetime import UTC
from datetime import datetime

import pytest

from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.services.decision.context import build_snapshot
from normative_conformance.services.observation.load_case_speech import IngestedObservation


def _ingested(*, observation_id, sequence, start_second, end_second):
    return IngestedObservation(
        observation_key=sequence,
        sequence=sequence,
        received_at=datetime.fromtimestamp(end_second, UTC),
        observation=ObservationInput(
            case_id="case",
            observation_id=observation_id,
            speaker_id="A",
            start_at=datetime.fromtimestamp(start_second, UTC),
            end_at=datetime.fromtimestamp(end_second, UTC),
            transcript="Hello",
            signal_level_min=-40,
            signal_level_avg=-30,
            signal_level_max=-20,
        ),
    )


def test_snapshot_orders_the_batch_by_time_and_excludes_later_speech():
    ingested = [
        _ingested(observation_id="handled", sequence=1, start_second=10, end_second=11),
        _ingested(observation_id="late", sequence=2, start_second=20, end_second=21),
        # Arrived after "late", but was spoken before it.
        _ingested(observation_id="early", sequence=3, start_second=15, end_second=16),
        _ingested(observation_id="after-batch", sequence=4, start_second=22, end_second=23),
    ]
    snapshot = build_snapshot(
        case_id="case",
        target_speaker_id="A",
        target_revision=2,
        ingested=ingested,
        after_sequence=1,
        through_sequence=3,
        context_seconds=30,
        captured_at=datetime(1970, 1, 1, minute=2, tzinfo=UTC),
    )
    assert snapshot.model_dump(include={"case_id", "target_speaker_id", "target_revision"}) == {
        "case_id": "case",
        "target_speaker_id": "A",
        "target_revision": 2,
    }
    assert (snapshot.after_sequence, snapshot.through_sequence) == (1, 3)
    assert [row.observation_id for row in snapshot.observations] == ["handled", "early", "late"]
    assert snapshot.new_observation_ids == ["early", "late"]
    assert snapshot.observations[0] == ingested[0].observation


@pytest.mark.parametrize(
    "context_seconds,expected",
    [
        pytest.param(5, ["recent", "new"], id="recent-speech-is-context"),
        pytest.param(0, ["new"], id="no-context"),
    ],
)
def test_context_is_handled_speech_ending_shortly_before_the_new_speech(context_seconds, expected):
    snapshot = build_snapshot(
        case_id="case",
        target_speaker_id="A",
        target_revision=1,
        ingested=[
            _ingested(observation_id="old", sequence=1, start_second=0, end_second=4),
            _ingested(observation_id="recent", sequence=2, start_second=4, end_second=6),
            _ingested(observation_id="new", sequence=3, start_second=10, end_second=11),
        ],
        after_sequence=2,
        through_sequence=3,
        context_seconds=context_seconds,
        captured_at=datetime(1970, 1, 1, minute=2, tzinfo=UTC),
    )
    assert [row.observation_id for row in snapshot.observations] == expected
    assert snapshot.new_observation_ids == ["new"]
