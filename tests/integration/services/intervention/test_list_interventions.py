from normative_conformance import models
from normative_conformance.services.intervention.list_interventions import list_interventions


def test_reads_stored_interventions_with_case_status_and_id_filters(*, session):
    session.add_all(
        models.CaseLog(case_id=case_id, created_at_us=0) for case_id in ("case", "other")
    )
    session.flush()
    first = models.Intervention(case_id="case", message="First", created_at_us=1, sent_at_us=2)
    second = models.Intervention(case_id="case", message="Second", created_at_us=3)
    other = models.Intervention(case_id="other", message="Other", created_at_us=4)
    session.add_all([first, second, other])
    session.commit()

    # Raw reads need neither experiment configuration nor response provenance.
    assert list_interventions(session=session) == [first, second, other]
    assert list_interventions(case_id="case", session=session) == [first, second]
    assert list_interventions(case_id="missing", session=session) == []
    assert list_interventions(status="pending", session=session) == [second, other]
    assert list_interventions(status="sent", session=session) == [first]
    assert list_interventions(
        intervention_ids=[other.intervention_id, first.intervention_id], session=session
    ) == [first, other]
    assert list_interventions(intervention_ids=[], session=session) == []
    assert (
        list_interventions(
            case_id="case",
            status="pending",
            intervention_ids=[first.intervention_id],
            session=session,
        )
        == []
    )
