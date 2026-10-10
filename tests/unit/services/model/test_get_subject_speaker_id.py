from unittest.mock import Mock

import pytest
from sqlmodel import Session

from normative_conformance.errors import NotReady
from normative_conformance.models.case import ExperimentConfig
from normative_conformance.services.model.get_subject_speaker_id import get_subject_speaker_id


@pytest.mark.parametrize("subject", [None, "configured-subject"])
def test_requires_the_singleton_experiment_configuration(*, subject):
    session = Mock(spec=Session)
    session.get.return_value = (
        None if subject is None else ExperimentConfig(subject_speaker_id=subject, created_at_us=1)
    )
    if subject is None:
        with pytest.raises(NotReady, match=r"^The experiment has not been configured$"):
            get_subject_speaker_id(session=session)
    else:
        assert get_subject_speaker_id(session=session) == subject
    session.get.assert_called_once_with(ExperimentConfig, 1)
