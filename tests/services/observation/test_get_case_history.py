from normative_conformance.models.case import CaseLog
from normative_conformance.models.observation import Observation
from normative_conformance.services.observation.get_case_history import get_case_history


def test_reads_only_the_requested_case_prefix_in_sequence_order(*, add_observation, session):
    first = add_observation(start=3, end=4)
    second = add_observation(start=1, end=2)
    add_observation(start=5, end=6)
    session.add(CaseLog(case_id="other", created_at_us=0))
    session.flush()
    session.add(Observation(**(first.model_dump() | {"case_id": "other"})))
    session.commit()

    history = get_case_history(case_id="case", through_sequence=2, session=session)

    assert history == [first, second]


def test_unknown_case_has_no_history(*, session):
    assert get_case_history(case_id="missing", through_sequence=1, session=session) == []
