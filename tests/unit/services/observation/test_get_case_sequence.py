from unittest.mock import Mock

import pytest
from sqlmodel import Session

from normative_conformance.errors import NotFound
from normative_conformance.services.observation.get_case_sequence import get_case_sequence


@pytest.mark.parametrize("sequence", [None, 7])
def test_requires_a_committed_observation_in_the_requested_case(*, sequence):
    session = Mock(spec=Session)
    session.exec.return_value.one.return_value = sequence
    if sequence is None:
        with pytest.raises(NotFound, match=r"^The case has no observations$"):
            get_case_sequence(case_id="requested", session=session)
    else:
        assert get_case_sequence(case_id="requested", session=session) == 7
    query = session.exec.call_args.args[0].compile()
    assert query.params == {"case_id_1": "requested"}
    assert "max(observation.sequence)" in str(query)
