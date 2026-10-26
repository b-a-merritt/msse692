from unittest.mock import Mock

import pytest
from sqlmodel import Session

from normative_conformance.services.observation.get_case_sequence import get_case_sequence


@pytest.mark.parametrize("stored,expected", [(None, 0), (7, 7)])
def test_returns_the_last_sequence_or_zero_before_speech(*, stored, expected):
    session = Mock(spec=Session)
    session.exec.return_value.one.return_value = stored
    assert get_case_sequence(case_id="requested", session=session) == expected
