from normative_conformance import models
from normative_conformance.models.assessment import Assessment
from normative_conformance.models.case import CaseLog
from normative_conformance.models.observation import Observation
from normative_conformance.services.assessment.list_assessments import list_assessments


def test_reads_case_history_in_id_order(*, session):
    case = models.CaseLog(case_id="case", created_at_us=1)
    session.add(case)
    session.flush()
    observation = models.Observation(
        case_id="case",
        observation_id="chunk",
        sequence=1,
        received_at_us=10,
        speaker_id="subject",
        start_at_us=1,
        end_at_us=9,
        transcript="Hello",
        signal_level_min=-30.0,
        signal_level_avg=-20.0,
        signal_level_max=-10.0,
    )
    session.add(observation)
    session.flush()
    model = models.NormativeModelVersion(
        model_id="anger",
        name="Anger",
        version="1",
        rules_json='[{"rule_id":"test"}]',
        parameters_json="{}",
    )
    session.add(model)
    session.flush()
    assessment = models.Assessment(
        evaluation_id="evaluation-1",
        case_id="case",
        model_id="anger",
        model_version="1",
        evaluated_at_us=11,
        through_sequence=1,
        status="conformant",
        explanation_json='{"reason_code":"satisfied"}',
    )
    session.add(assessment)
    session.flush()
    session.commit()
    session.expunge_all()
    records = {"assessment": assessment, "case": case, "model": model, "observation": observation}

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


def test_pending_work_excludes_assessments_with_a_resolution(*, session):
    case = models.CaseLog(case_id="case", created_at_us=1)
    session.add(case)
    session.flush()
    observation = models.Observation(
        case_id="case",
        observation_id="chunk",
        sequence=1,
        received_at_us=10,
        speaker_id="subject",
        start_at_us=1,
        end_at_us=9,
        transcript="Hello",
        signal_level_min=-30.0,
        signal_level_avg=-20.0,
        signal_level_max=-10.0,
    )
    session.add(observation)
    session.flush()
    model = models.NormativeModelVersion(
        model_id="anger",
        name="Anger",
        version="1",
        rules_json='[{"rule_id":"test"}]',
        parameters_json="{}",
    )
    session.add(model)
    session.flush()
    assessment = models.Assessment(
        evaluation_id="evaluation-1",
        case_id="case",
        model_id="anger",
        model_version="1",
        evaluated_at_us=11,
        through_sequence=1,
        status="conformant",
        explanation_json='{"reason_code":"satisfied"}',
    )
    session.add(assessment)
    session.flush()
    session.commit()
    session.expunge_all()
    records = {"assessment": assessment, "case": case, "model": model, "observation": observation}

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


def test_case_history_excludes_other_cases(*, session):
    case = models.CaseLog(case_id="case", created_at_us=1)
    session.add(case)
    session.flush()
    observation = models.Observation(
        case_id="case",
        observation_id="chunk",
        sequence=1,
        received_at_us=10,
        speaker_id="subject",
        start_at_us=1,
        end_at_us=9,
        transcript="Hello",
        signal_level_min=-30.0,
        signal_level_avg=-20.0,
        signal_level_max=-10.0,
    )
    session.add(observation)
    session.flush()
    model = models.NormativeModelVersion(
        model_id="anger",
        name="Anger",
        version="1",
        rules_json='[{"rule_id":"test"}]',
        parameters_json="{}",
    )
    session.add(model)
    session.flush()
    assessment = models.Assessment(
        evaluation_id="evaluation-1",
        case_id="case",
        model_id="anger",
        model_version="1",
        evaluated_at_us=11,
        through_sequence=1,
        status="conformant",
        explanation_json='{"reason_code":"satisfied"}',
    )
    session.add(assessment)
    session.flush()
    session.commit()
    session.expunge_all()
    records = {"assessment": assessment, "case": case, "model": model, "observation": observation}

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
