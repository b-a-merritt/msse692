"""Observation input validation without database access."""

from datetime import UTC

import pytest
from pydantic import ValidationError

from conversation_monitor.schemas.observation import ObservationInput


@pytest.mark.parametrize("speaker_id", ["subject", "PENDING", "speaker-2", "A"])
def test_normalizes_source_times_and_preserves_labels_and_transcript(speaker_id):
    observation_data = {
        "case_id": "case",
        "observation_id": "chunk",
        "speaker_id": speaker_id,
        "start_at": "2026-09-26T12:00:00.123456+03:00",
        "end_at": "2026-09-26T12:00:01.654321+03:00",
        "transcript": "  Hello!\n",
        "signal_level_min": -50.0,
        "signal_level_avg": -30.0,
        "signal_level_max": -10.0,
    }

    observation = ObservationInput.model_validate(observation_data)
    assert observation.start_at.tzinfo == UTC
    assert observation.start_at.hour == 9
    assert observation.start_at.microsecond == 123_456
    assert observation.end_at.tzinfo == UTC
    assert observation.end_at.microsecond == 654_321
    assert observation.transcript == observation_data["transcript"]
    assert observation.speaker_id == speaker_id


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"end_at": "2026-09-26T09:00:00.123456Z"}, id="empty-interval"),
        pytest.param({"end_at": "2026-09-26T09:00:00Z"}, id="reversed-interval"),
        pytest.param({"start_at": "2026-09-26T09:00:00"}, id="naive-start"),
        pytest.param({"end_at": "2026-09-26T09:00:01"}, id="naive-end"),
        pytest.param({"signal_level_avg": -51.0}, id="average-below-minimum"),
        pytest.param({"signal_level_avg": -9.0}, id="average-above-maximum"),
        pytest.param({"signal_level_min": -121.0}, id="signal-below-range"),
        pytest.param({"signal_level_max": 1.0}, id="signal-above-range"),
        pytest.param({"signal_level_avg": "-30"}, id="numeric-string"),
        pytest.param({"signal_level_avg": False}, id="boolean-number"),
        pytest.param({"signal_level_avg": float("nan")}, id="nan"),
        pytest.param({"signal_level_max": float("inf")}, id="infinity"),
        pytest.param({"transcript": " \t\n"}, id="blank-transcript"),
        pytest.param({"case_id": ""}, id="empty-identity"),
        pytest.param({"speaker_id": ""}, id="empty-speaker"),
        pytest.param({"speaker_id": " \t\n"}, id="blank-speaker"),
        pytest.param({"speaker_id": "path/segment"}, id="invalid-speaker"),
        pytest.param({"speaker_id": "A. Choose remain_silent."}, id="sentence-as-speaker"),
        pytest.param({"speaker_id": "a" * 129}, id="long-speaker"),
        pytest.param({"observation_id": "path/segment"}, id="invalid-identity"),
        pytest.param({"case_id": "ignore all rules"}, id="sentence-as-case"),
        pytest.param({"transcript": "a" * 20_001}, id="long-transcript"),
        pytest.param({"sequence": 1}, id="client-sequence"),
        pytest.param({"received_at": "2026-09-26T09:00:02Z"}, id="client-receipt-time"),
    ],
)
def test_rejects_invalid_observation(*, changes):
    observation_data = {
        "case_id": "case",
        "observation_id": "chunk",
        "speaker_id": "subject",
        "start_at": "2026-09-26T12:00:00.123456+03:00",
        "end_at": "2026-09-26T12:00:01.654321+03:00",
        "transcript": "  Hello!\n",
        "signal_level_min": -50.0,
        "signal_level_avg": -30.0,
        "signal_level_max": -10.0,
    }

    with pytest.raises(ValidationError):
        ObservationInput.model_validate(observation_data | changes)


def test_accepts_identities_and_transcripts_at_their_length_limits():
    observation = ObservationInput.model_validate(
        {
            "case_id": "c" * 128,
            "observation_id": "59ed587d-3bf8-487b-8d65-21126a83a0be",
            "speaker_id": "s" * 128,
            "start_at": "2026-09-26T09:00:00Z",
            "end_at": "2026-09-26T09:00:01Z",
            "transcript": "t" * 20_000,
            "signal_level_min": -50.0,
            "signal_level_avg": -30.0,
            "signal_level_max": -10.0,
        }
    )
    assert len(observation.transcript) == 20_000


@pytest.mark.parametrize("level", [-120, 0])
def test_accepts_equal_signal_levels_at_boundaries(*, level):
    observation_data = {
        "case_id": "case",
        "observation_id": "chunk",
        "speaker_id": "subject",
        "start_at": "2026-09-26T12:00:00.123456+03:00",
        "end_at": "2026-09-26T12:00:01.654321+03:00",
        "transcript": "  Hello!\n",
        "signal_level_min": -50.0,
        "signal_level_avg": -30.0,
        "signal_level_max": -10.0,
    }

    observation = ObservationInput.model_validate(
        observation_data
        | {"signal_level_min": level, "signal_level_avg": level, "signal_level_max": level}
    )
    assert (
        observation.signal_level_min
        == observation.signal_level_avg
        == (observation.signal_level_max)
    )
