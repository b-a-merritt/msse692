from normative_conformance.models.assessment import Assessment
from normative_conformance.models.case import CaseLog
from normative_conformance.models.observation import Observation
from normative_conformance.services.assessment.list_assessments import list_assessments


def test_reads_case_history_in_id_order(*, records, session):
    original = records["assessment"]
    later = Assessment(
        **(
            original.model_dump()
            | {"assessment_id": None, "evaluation_id": "later", "evaluated_at_us": 1}
        )
    )
    session.add(later)
    session.commit()

    results = list_assessments(session=session, case_id="case")
    assert [row.assessment_id for row in results] == [original.assessment_id, later.assessment_id]
    assert list_assessments(session=session, case_id="other") == []

    assert list_assessments(session=session, evaluation_id=original.evaluation_id) == [original]
    assert list_assessments(session=session, evaluation_id="later") == [later]
    assert list_assessments(session=session, case_id="other", evaluation_id="later") == []


def test_pending_work_excludes_assessments_with_a_resolution(*, records, session):
    values = records["assessment"].model_dump() | {
        "assessment_id": None,
        "status": "pending",
        "next_due_at_us": 20,
    }
    resolved = Assessment(**(values | {"evaluation_id": "resolved"}))
    pending = Assessment(**(values | {"evaluation_id": "pending"}))
    session.add_all([resolved, pending])
    session.flush()
    resolution = Assessment(
        **(
            values
            | {
                "evaluation_id": "resolution",
                "status": "non-conformant",
                "evaluated_at_us": 20,
                "next_due_at_us": None,
                "resolves_assessment_id": resolved.assessment_id,
            }
        )
    )
    session.add(resolution)
    session.commit()

    results = list_assessments(session=session, status="pending", unresolved=True)
    assert [row.assessment_id for row in results] == [pending.assessment_id]
    results = list_assessments(session=session, case_id="case", status="pending")
    assert [row.assessment_id for row in results] == [resolved.assessment_id, pending.assessment_id]


def test_case_history_excludes_other_cases(*, records, session):
    original = records["assessment"]
    session.add(CaseLog(case_id="other", created_at_us=1))
    session.flush()
    session.add(Observation(**(records["observation"].model_dump() | {"case_id": "other"})))
    session.flush()
    other = Assessment(
        **(
            original.model_dump()
            | {"assessment_id": None, "evaluation_id": "other", "case_id": "other"}
        )
    )
    session.add(other)
    session.commit()

    assert list_assessments(session=session, case_id="case") == [original]
    assert list_assessments(session=session, case_id="other") == [other]
    assert list_assessments(session=session) == [original, other]
