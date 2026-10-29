from unittest.mock import Mock

from sqlmodel import Session

from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.services.observation.stage_correction import stage_correction


def test_adds_revised_speech_without_a_sequence_or_commit():
    session = Mock(spec=Session)
    observation = ObservationInput(
        case_id="case",
        observation_id="regrouped",
        speaker_id="B",
        start_at="1970-01-01T00:00:01Z",
        end_at="1970-01-01T00:00:01.100000Z",
        transcript="Hello",
        signal_level_min=-50,
        signal_level_avg=-30,
        signal_level_max=-10,
    )

    stage_correction(observation=observation, speaker_revision_id=7, session=session)

    [row] = [call.args[0] for call in session.add.call_args_list]
    assert row.model_dump() == {
        "observation_key": None,
        "case_id": "case",
        "observation_id": "regrouped",
        "speaker_revision_id": 7,
        "sequence": None,
        "received_at_us": None,
        "speaker_id": "B",
        "start_at_us": 1_000_000,
        "end_at_us": 1_100_000,
        "transcript": "Hello",
        "signal_level_min": -50,
        "signal_level_avg": -30,
        "signal_level_max": -10,
    }
    session.commit.assert_not_called()
