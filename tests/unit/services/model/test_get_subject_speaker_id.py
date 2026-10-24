from unittest.mock import Mock

import pytest
from sqlmodel import Session

from normative_conformance.errors import NotFound
from normative_conformance.models.case import CaseLog
from normative_conformance.services.model.get_subject_speaker_id import get_subject_speaker_id


@pytest.mark.parametrize("target", [None, "configured-subject"])
def test_reads_only_the_requested_case_target(target):
    session = Mock(spec=Session)
    session.get.return_value = CaseLog(case_id="second", created_at_us=1, target_speaker_id=target)
    assert get_subject_speaker_id(case_id="second", session=session) == target
    session.get.assert_called_once_with(CaseLog, "second")


def test_missing_case_is_not_found():
    session = Mock(spec=Session)
    session.get.return_value = None
    with pytest.raises(NotFound, match="The case does not exist"):
        get_subject_speaker_id(case_id="missing", session=session)
