from unittest.mock import Mock

from sqlmodel import Session

from normative_conformance.models.observation import Observation
from normative_conformance.services.observation.get_case_history import get_case_history


def test_requests_an_inclusive_case_prefix_in_arrival_order():
    rows = [Observation(case_id="case", observation_id="first", sequence=1)]
    session = Mock(spec=Session)
    session.exec.return_value.all.return_value = rows
    assert get_case_history(case_id="case", through_sequence=3, session=session) == rows
    query = session.exec.call_args.args[0].compile()
    assert query.params == {"case_id_1": "case", "sequence_1": 3}
    assert "observation.sequence <=" in str(query)
    assert "ORDER BY observation.sequence" in str(query)
