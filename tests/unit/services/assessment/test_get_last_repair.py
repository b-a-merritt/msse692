from unittest.mock import Mock

from sqlmodel import Session

from normative_conformance.models.observation import Observation
from normative_conformance.services.assessment.get_last_repair import get_last_repair


def test_selects_latest_confirmed_repair_in_speech_order():
    session = Mock(spec=Session)
    repair = Observation(case_id="case", observation_id="repair", sequence=3)
    session.exec.return_value.first.return_value = repair
    assert get_last_repair(case_id="case", session=session) is repair
    query = session.exec.call_args.args[0].compile()
    assert query.params == {
        "case_id_1": "case",
        "type_1": "repairs",
        "status_1": "conformant",
        "param_1": 1,
    }
    assert (
        "observation.start_at_us DESC, observation.end_at_us DESC, observation.sequence DESC"
        in str(query)
    )
