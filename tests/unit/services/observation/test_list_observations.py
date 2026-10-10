from datetime import datetime
from datetime import timezone
from unittest.mock import Mock

from sqlmodel import Session

from normative_conformance.models.observation import Observation
from normative_conformance.services.observation.list_observations import list_observations


def test_converts_stored_microseconds_without_changing_transcript():
    session = Mock(spec=Session)
    session.exec.return_value = [
        Observation(
            case_id="case",
            observation_id="chunk",
            sequence=2,
            received_at_us=10,
            speaker_id="subject",
            start_at_us=-1,
            end_at_us=1,
            transcript=" Hello ",
            signal_level_min=-50,
            signal_level_avg=-30,
            signal_level_max=-10,
        )
    ]
    result = list_observations(case_id="case", session=session)
    assert result[0].model_dump() == {
        "case_id": "case",
        "observation_id": "chunk",
        "sequence": 2,
        "received_at": datetime(1970, 1, 1, 0, 0, 0, 10, tzinfo=timezone.utc),
        "speaker_id": "subject",
        "start_at": datetime(1969, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc),
        "end_at": datetime(1970, 1, 1, 0, 0, 0, 1, tzinfo=timezone.utc),
        "transcript": " Hello ",
        "signal_level_min": -50,
        "signal_level_avg": -30,
        "signal_level_max": -10,
    }
    query = session.exec.call_args.args[0].compile()
    assert query.params == {"case_id_1": "case"}
    assert "ORDER BY observation.sequence DESC" in str(query)
