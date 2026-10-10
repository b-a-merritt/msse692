"""Observation input validation without database access."""

from datetime import timezone

import pytest
from pydantic import ValidationError

from normative_conformance.schemas.observation import ObservationInput


def test_normalizes_source_times_to_utc_and_preserves_transcript():
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

    observation = ObservationInput.model_validate(observation_data)
    assert observation.start_at.tzinfo == timezone.utc
    assert observation.start_at.hour == 9
    assert observation.start_at.microsecond == 123_456
    assert observation.end_at.tzinfo == timezone.utc
    assert observation.end_at.microsecond == 654_321
    assert observation.transcript == observation_data["transcript"]


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
        pytest.param({"observation_id": "path/segment"}, id="invalid-identity"),
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
