from datetime import datetime
from datetime import timezone
from unittest.mock import Mock

from sqlmodel import Session

from normative_conformance.models.observation import Observation
from normative_conformance.services.observation.load_case_speech import load_case_speech


def test_ingested_rows_keep_their_key_sequence_and_receipt_time():
    row = Observation(
        observation_key=7,
        case_id="case",
        observation_id="turn",
        sequence=3,
        received_at_us=2_000_000,
        speaker_id="A",
        start_at_us=0,
        end_at_us=1_000_000,
        transcript="Hello",
        signal_level_min=-40,
        signal_level_avg=-30,
        signal_level_max=-20,
    )
    session = Mock(spec=Session)
    session.exec.return_value.all.return_value = [row]

    [speech] = load_case_speech(case_id="case", session=session)

    assert (speech.observation_key, speech.sequence) == (7, 3)
    assert speech.received_at == datetime(1970, 1, 1, second=2, tzinfo=timezone.utc)
    assert speech.observation.model_dump(include={"observation_id", "speaker_id"}) == {
        "observation_id": "turn",
        "speaker_id": "A",
    }
