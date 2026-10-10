from normative_conformance import models
from normative_conformance.models.assessment import Assessment
from normative_conformance.models.case import CaseLog
from normative_conformance.models.observation import Observation
from normative_conformance.services.assessment.load_repair_deadlines import load_repair_deadlines


def test_loads_only_earliest_unresolved_pending_deadlines(*, session, engine):
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


def test_no_pending_assessments_returns_no_deadlines(*, session, engine):
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

    assert load_repair_deadlines(engine=engine) == {}
