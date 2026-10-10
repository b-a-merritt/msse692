from itertools import count
from uuid import uuid4

from normative_conformance import models
from normative_conformance.database import read_session
from normative_conformance.schemas.assessment import CaseSnapshot
from normative_conformance.services.assessment.create_assessment import create_assessment
from normative_conformance.services.assessment.list_assessments import list_assessments
from normative_conformance.services.model.get_model import get_model
from normative_conformance.services.observation.get_case_sequence import get_case_sequence

from ...storage import persist


def test_append_flushes_without_committing(*, session, engine):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)

    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=1_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )

    row = create_assessment(
        model=get_model(model_id="apology", version="1", session=session),
        snapshot=CaseSnapshot(
            case_id="case",
            evaluation_id=str(uuid4()),
            through_sequence=get_case_sequence(case_id="case", session=session),
            evaluated_at_us=100_000_000,
        ),
        status="conformant",
        session=session,
    )

    assert row.assessment_id is not None
    assert list_assessments(session=session) == [row]
    with read_session(engine=engine) as reader:
        assert list_assessments(session=reader) == []

    session.rollback()
    assert list_assessments(session=session) == []
