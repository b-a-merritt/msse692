from normative_conformance.models.observation import Observation
from normative_conformance.services.observation.records import to_record


def test_records_convert_microseconds_to_utc_and_preserve_evidence():
    row = Observation(
        case_id="case",
        observation_id="word",
        sequence=1,
        received_at_us=10,
        speaker_id="A",
        start_at_us=1,
        end_at_us=9,
        transcript="Hello",
        signal_level_min=-50,
        signal_level_avg=-30,
        signal_level_max=-10,
    )
    result = to_record(observation=row)
    assert result.model_dump(mode="json") == {
        "case_id": "case",
        "observation_id": "word",
        "sequence": 1,
        "received_at": "1970-01-01T00:00:00.000010Z",
        "updated_at": "1970-01-01T00:00:00.000010Z",
        "speaker_id": "A",
        "start_at": "1970-01-01T00:00:00.000001Z",
        "end_at": "1970-01-01T00:00:00.000009Z",
        "transcript": "Hello",
        "signal_level_min": -50,
        "signal_level_avg": -30,
        "signal_level_max": -10,
    }
