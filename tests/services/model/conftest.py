import pytest
from sqlmodel import select

from normative_conformance.models.observation import Observation
from normative_conformance.services.model.evaluate_model import evaluate_model
from normative_conformance.services.model.get_model import get_model
from normative_conformance.services.model.get_subject_speaker_id import get_subject_speaker_id


@pytest.fixture
def matches(*, session):
    def matches(*, model_id, through_sequence=None, after=None, deadline=None):
        rows = session.exec(select(Observation)).all()
        return evaluate_model(
            model=get_model(model_id=model_id, version="1", session=session),
            case_id="case",
            subject_speaker_id=get_subject_speaker_id(session=session),
            through_sequence=through_sequence if through_sequence is not None else len(rows),
            session=session,
            after_observation=after,
            deadline_at_us=deadline,
        )

    return matches
