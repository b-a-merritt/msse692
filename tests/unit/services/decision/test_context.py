from datetime import datetime
from datetime import timezone

import pytest

from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.schemas.observation import ObservationRecord
from normative_conformance.schemas.observation import ObservationReplacement
from normative_conformance.services.decision.context import build_snapshot


def test_latest_revision_replaces_originals_before_time_order_and_context_filtering():
    first = ObservationRecord(
        case_id="case",
        observation_id="one",
        sequence=1,
        speaker_id="A",
        start_at="1970-01-01T00:00:10Z",
        end_at="1970-01-01T00:00:11Z",
        transcript="Hello",
        signal_level_min=-40,
        signal_level_avg=-30,
        signal_level_max=-20,
        received_at="1970-01-01T00:01:00Z",
        updated_at="1970-01-01T00:01:00Z",
    )
    second = first.model_copy(update={"observation_id": "two", "sequence": 2})
    new = first.model_copy(
        update={
            "observation_id": "new",
            "sequence": 3,
            "start_at": datetime(1970, 1, 1, second=20, tzinfo=timezone.utc),
            "end_at": datetime(1970, 1, 1, second=21, tzinfo=timezone.utc),
        }
    )
    stale = first.model_copy(
        update={
            "observation_id": "stale",
            "sequence": 4,
            "start_at": datetime(1970, 1, 1, tzinfo=timezone.utc),
            "end_at": datetime(1970, 1, 1, second=1, tzinfo=timezone.utc),
        }
    )
    future = first.model_copy(update={"observation_id": "future", "sequence": 5})
    replacement = ObservationInput(
        case_id="case",
        observation_id="merged-B",
        speaker_id="B",
        start_at="1970-01-01T00:00:10Z",
        end_at="1970-01-01T00:00:11Z",
        transcript="Hello yes",
        signal_level_min=-40,
        signal_level_avg=-30,
        signal_level_max=-20,
    )
    revisions = [
        ObservationReplacement(
            replaced_observation_ids=["one", "two"],
            observations=[
                replacement.model_copy(update={"observation_id": "superseded", "speaker_id": "A"})
            ],
        ),
        ObservationReplacement(replaced_observation_ids=["two", "one"], observations=[replacement]),
        ObservationReplacement(
            replaced_observation_ids=["future"],
            observations=[replacement.model_copy(update={"observation_id": "future-revised"})],
        ),
    ]
    snapshot = build_snapshot(
        case_id="case",
        target_speaker_id="A",
        target_revision=1,
        observations=[first, second, new, stale, future],
        revisions=revisions,
        after_sequence=2,
        through_sequence=4,
        context_seconds=5,
        captured_at=datetime(1970, 1, 1, minute=2, tzinfo=timezone.utc),
    )
    # New arrivals are always included, even when their speech precedes the context window.
    assert [row.observation_id for row in snapshot.observations] == ["stale", "merged-B", "new"]
    assert snapshot.new_observation_ids == ["stale", "new"]
    assert snapshot.observations[1] == replacement
    assert first.speaker_id == "A"


@pytest.mark.parametrize(
    "after,through,seconds,expected",
    [
        (0, 1, 30, "one-B"),
        (1, 2, 0, "two"),
    ],
)
def test_corrected_new_rows_and_context_cutoff(after, through, seconds, expected):
    original = ObservationRecord(
        case_id="case",
        observation_id="one",
        sequence=1,
        speaker_id="A",
        start_at="1970-01-01T00:00:00Z",
        end_at="1970-01-01T00:00:01Z",
        transcript="Hello",
        signal_level_min=-40,
        signal_level_avg=-30,
        signal_level_max=-20,
        received_at="1970-01-01T00:01:00Z",
        updated_at="1970-01-01T00:01:00Z",
    )
    second = original.model_copy(
        update={
            "observation_id": "two",
            "sequence": 2,
            "start_at": datetime(1970, 1, 1, second=10, tzinfo=timezone.utc),
            "end_at": datetime(1970, 1, 1, second=11, tzinfo=timezone.utc),
        }
    )
    replacement = ObservationInput(
        case_id="case",
        observation_id="one-B",
        speaker_id="B",
        start_at=original.start_at,
        end_at=original.end_at,
        transcript="Hello",
        signal_level_min=-40,
        signal_level_avg=-30,
        signal_level_max=-20,
    )
    snapshot = build_snapshot(
        case_id="case",
        target_speaker_id="B",
        target_revision=2,
        observations=[original, second],
        revisions=[
            ObservationReplacement(replaced_observation_ids=["one"], observations=[replacement])
        ],
        after_sequence=after,
        through_sequence=through,
        context_seconds=seconds,
        captured_at=datetime(1970, 1, 1, minute=2, tzinfo=timezone.utc),
    )
    assert snapshot.new_observation_ids == [expected]
    assert [row.observation_id for row in snapshot.observations] == [expected]


def test_correction_spanning_handled_speech_is_new_only_where_speech_is_unhandled():
    handled = ObservationRecord(
        case_id="case",
        observation_id="handled",
        sequence=1,
        speaker_id="A",
        start_at="1970-01-01T00:00:00Z",
        end_at="1970-01-01T00:00:01Z",
        transcript="Hello",
        signal_level_min=-40,
        signal_level_avg=-30,
        signal_level_max=-20,
        received_at="1970-01-01T00:01:00Z",
        updated_at="1970-01-01T00:01:00Z",
    )
    unhandled = handled.model_copy(
        update={
            "observation_id": "unhandled",
            "sequence": 2,
            "start_at": datetime(1970, 1, 1, second=1, tzinfo=timezone.utc),
            "end_at": datetime(1970, 1, 1, second=2, tzinfo=timezone.utc),
        }
    )
    corrected = ObservationInput(
        case_id="case",
        observation_id="handled-B",
        speaker_id="B",
        start_at=handled.start_at,
        end_at=handled.end_at,
        transcript="Hello",
        signal_level_min=-40,
        signal_level_avg=-30,
        signal_level_max=-20,
    )
    snapshot = build_snapshot(
        case_id="case",
        target_speaker_id="A",
        target_revision=1,
        observations=[handled, unhandled],
        revisions=[
            ObservationReplacement(
                replaced_observation_ids=["handled", "unhandled"],
                observations=[
                    corrected,
                    corrected.model_copy(
                        update={
                            "observation_id": "unhandled-B",
                            "start_at": unhandled.start_at,
                            "end_at": unhandled.end_at,
                        }
                    ),
                ],
            )
        ],
        after_sequence=1,
        through_sequence=2,
        context_seconds=30,
        captured_at=datetime(1970, 1, 1, minute=2, tzinfo=timezone.utc),
    )
    assert [row.observation_id for row in snapshot.observations] == ["handled-B", "unhandled-B"]
    assert snapshot.new_observation_ids == ["unhandled-B"]


def test_revision_that_removes_all_new_speech_leaves_nothing_to_assess():
    removed = ObservationRecord(
        case_id="case",
        observation_id="removed",
        sequence=1,
        speaker_id="A",
        start_at="1970-01-01T00:00:00Z",
        end_at="1970-01-01T00:00:01Z",
        transcript="Hello",
        signal_level_min=-40,
        signal_level_avg=-30,
        signal_level_max=-20,
        received_at="1970-01-01T00:01:00Z",
        updated_at="1970-01-01T00:01:00Z",
    )
    snapshot = build_snapshot(
        case_id="case",
        target_speaker_id="A",
        target_revision=1,
        observations=[removed],
        revisions=[ObservationReplacement(replaced_observation_ids=["removed"], observations=[])],
        after_sequence=0,
        through_sequence=1,
        context_seconds=30,
        captured_at=datetime(1970, 1, 1, minute=2, tzinfo=timezone.utc),
    )
    assert (snapshot.through_sequence, snapshot.observations, snapshot.new_observation_ids) == (
        1,
        [],
        [],
    )
