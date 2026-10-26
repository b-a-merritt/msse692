from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest

from normative_conformance.errors import CaptureFailure
from normative_conformance.services.capture.levels import FrameLevel
from normative_conformance.services.capture.observations import build_observations
from normative_conformance.services.capture.transcriber import TurnUpdate
from normative_conformance.services.capture.transcriber import Word


def test_groups_consecutive_words_and_uses_overlapping_frames_without_duration_weighting():
    start = datetime(2026, 10, 26, tzinfo=timezone.utc)
    inputs = {
        "case_id": "case",
        "session_id": "session",
        "started_at": start,
        "frames": [
            FrameLevel(start_ms=offset, end_ms=offset + 20, dbfs=level)
            for offset, level in [(0, -60), (20, -20), (40, -40), (60, -10), (80, -5)]
        ],
    }
    turn = TurnUpdate(
        turn_order=1,
        final=True,
        speaker_id="A",
        transcript="Hello there yes again",
        words=(
            Word("Hello", 5, 15, "A"),
            Word("there", 15, 25, "A"),
            Word("yes", 40, 60, "B"),
            Word("again", 60, 80, "A"),
        ),
    )
    rows = build_observations(**inputs, turn=turn)
    assert [r.speaker_id for r in rows] == ["A", "B", "A"]
    assert [r.transcript for r in rows] == ["Hello there", "yes", "again"]
    assert [r.signal_level_avg for r in rows] == [-40, -40, -10]
    assert (rows[0].signal_level_min, rows[0].signal_level_max) == (-60, -20)
    assert rows[0].start_at == start + timedelta(milliseconds=5)
    assert rows[0].end_at == start + timedelta(milliseconds=25)
    assert len({r.observation_id for r in rows}) == 3
    assert all(r.case_id == "case" for r in rows)
    assert build_observations(**inputs, turn=turn) == rows
    other_session = build_observations(**(inputs | {"session_id": "another"}), turn=turn)
    assert {r.observation_id for r in rows}.isdisjoint(r.observation_id for r in other_session)


def test_unresolved_words_do_not_inherit_dominant_speaker():
    inputs = {
        "case_id": "case",
        "session_id": "s",
        "started_at": datetime(2026, 10, 26, tzinfo=timezone.utc),
        "frames": [FrameLevel(start_ms=0, end_ms=100, dbfs=-30)],
    }
    rows = build_observations(
        **inputs,
        turn=TurnUpdate(
            turn_order=0,
            final=True,
            speaker_id="A",
            transcript="one two three",
            words=(
                Word("one", 0, 20, None),
                Word("two", 20, 40, None),
                Word("three", 40, 60, "B"),
            ),
        ),
    )
    assert [(r.speaker_id, r.transcript) for r in rows] == [
        ("PENDING", "one two"),
        ("B", "three"),
    ]


def test_partials_and_empty_final_turns_create_no_observations():
    inputs = {
        "case_id": "case",
        "session_id": "s",
        "started_at": datetime(2026, 10, 26, tzinfo=timezone.utc),
        "frames": [],
    }
    assert build_observations(**inputs, turn=TurnUpdate(0, False, "A", "Hello", ())) == []
    assert build_observations(**inputs, turn=TurnUpdate(0, True, None, "", ())) == []


@pytest.mark.parametrize(
    "words,transcript",
    [
        ((), "Words without timestamps"),
        ((Word("Hello", 20, 40, "A"),), "Hello"),  # No overlapping frame.
        ((Word("Hello", 10, 10, "A"),), "Hello"),  # Empty observation interval.
        ((Word("Hello", 10, 5, "A"),), "Hello"),
        ((Word(" ", 0, 10, "A"),), " "),
        ((Word("Hello", 0, 10, "bad/label"),), "Hello"),
    ],
)
def test_unusable_final_words_fail_without_inventing_observation_data(words, transcript):
    inputs = {
        "case_id": "case",
        "session_id": "s",
        "started_at": datetime(2026, 10, 26, tzinfo=timezone.utc),
        "frames": [FrameLevel(start_ms=0, end_ms=20, dbfs=-30)],
    }
    with pytest.raises(CaptureFailure) as caught:
        build_observations(**inputs, turn=TurnUpdate(0, True, "A", transcript, words))
    assert caught.value.code == "providerProtocol"


def test_timestamp_overflow_is_a_protocol_failure():
    inputs = {
        "case_id": "case",
        "session_id": "s",
        "started_at": datetime.max.replace(tzinfo=timezone.utc),
        "frames": [FrameLevel(start_ms=0, end_ms=20, dbfs=-30)],
    }
    with pytest.raises(CaptureFailure) as caught:
        build_observations(
            **inputs, turn=TurnUpdate(0, True, "A", "Hello", (Word("Hello", 0, 20, "A"),))
        )
    assert caught.value.code == "providerProtocol"
