from normative_conformance.models.assessment import Assessment
from normative_conformance.models.case import CaseLog
from normative_conformance.models.observation import Observation
from normative_conformance.services.assessment.load_repair_deadlines import load_repair_deadlines


def test_loads_only_earliest_unresolved_pending_deadlines(*, records, session, engine):
    values = records["assessment"].model_dump() | {"assessment_id": None, "status": "pending"}
    resolved = Assessment(**(values | {"evaluation_id": "resolved", "next_due_at_us": 5}))
    session.add_all(
        [
            resolved,
            Assessment(**(values | {"evaluation_id": "later", "next_due_at_us": 30})),
            Assessment(**(values | {"evaluation_id": "earlier", "next_due_at_us": 20})),
            CaseLog(case_id="other", created_at_us=0),
        ]
    )
    session.flush()
    session.add(Observation(**(records["observation"].model_dump() | {"case_id": "other"})))
    session.flush()
    session.add_all(
        [
            Assessment(
                **(
                    values
                    | {
                        "evaluation_id": "resolution",
                        "status": "non-conformant",
                        "resolves_assessment_id": resolved.assessment_id,
                    }
                )
            ),
            Assessment(
                **(values | {"evaluation_id": "other", "case_id": "other", "next_due_at_us": 10})
            ),
        ]
    )
    session.commit()

    assert load_repair_deadlines(engine=engine) == {"case": 20, "other": 10}


def test_no_pending_assessments_returns_no_deadlines(*, records, engine):
    assert load_repair_deadlines(engine=engine) == {}
