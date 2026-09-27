from normative_conformance.database import read_session
from normative_conformance.services.assessment.create_assessment import create_assessment
from normative_conformance.services.assessment.list_assessments import list_assessments
from normative_conformance.services.model.get_model import get_model


def test_append_flushes_without_committing(*, add_observation, snapshot, session, engine):
    add_observation(start=0, end=1)

    row = create_assessment(
        model=get_model(model_id="apology", version="1", session=session),
        snapshot=snapshot(),
        status="conformant",
        session=session,
    )

    assert row.assessment_id is not None
    assert list_assessments(session=session) == [row]
    with read_session(engine=engine) as reader:
        assert list_assessments(session=reader) == []

    session.rollback()
    assert list_assessments(session=session) == []
