import pytest

from normative_conformance.errors import NotReady
from normative_conformance.models.case import ExperimentConfig
from normative_conformance.services.model.get_subject_speaker_id import get_subject_speaker_id


def test_reads_the_configured_subject(*, session):
    session.add(ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.commit()

    assert get_subject_speaker_id(session=session) == "configured-subject"


def test_missing_configuration_is_not_ready(*, session):
    with pytest.raises(NotReady, match=r"^The experiment has not been configured$"):
        get_subject_speaker_id(session=session)
