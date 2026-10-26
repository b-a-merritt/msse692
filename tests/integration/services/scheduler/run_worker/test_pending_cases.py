from normative_conformance.models.assessment import Assessment
from normative_conformance.models.case import CaseLog
from normative_conformance.models.normative_model import NormativeModelVersion
from normative_conformance.models.observation import Observation
from normative_conformance.services.scheduler.run_worker.pending_cases import pending_cases


def test_only_resolved_cases_with_new_input_target_or_due_repair_are_ready(engine, session):
    handled = {"last_handled_sequence": 1, "target_speaker_id": "A"}
    cases = [
        CaseLog(case_id="new", created_at_us=0, target_speaker_id="A"),
        CaseLog(case_id="unresolved", created_at_us=0),
        CaseLog(case_id="handled", created_at_us=0, **handled),
        CaseLog(
            case_id="changed",
            created_at_us=0,
            target_speaker_id="B",
            last_handled_sequence=1,
            target_revision=2,
            last_handled_target_revision=1,
        ),
        CaseLog(case_id="empty", created_at_us=0, target_speaker_id="A", target_revision=1),
        CaseLog(case_id="due", created_at_us=0, **handled),
        CaseLog(case_id="later", created_at_us=0, **handled),
        CaseLog(case_id="resolved", created_at_us=0, **handled),
    ]
    session.add_all(cases)
    session.add(
        NormativeModelVersion(
            model_id="harm_phrase",
            version="pending-test",
            name="Harm",
            rules_json="[]",
            parameters_json="{}",
        )
    )
    session.flush()
    for case_id in ["new", "unresolved", "handled", "changed", "due", "later", "resolved"]:
        session.add(
            Observation(
                case_id=case_id,
                observation_id="one",
                sequence=1,
                received_at_us=0,
                updated_at_us=0,
                start_at_us=0,
                end_at_us=1,
                speaker_id="A",
                transcript="hello",
                signal_level_min=-40,
                signal_level_avg=-30,
                signal_level_max=-20,
            )
        )
    session.flush()
    pending = {
        case_id: Assessment(
            case_id=case_id,
            evaluation_id=case_id,
            subject_speaker_id="A",
            model_id="harm_phrase",
            model_version="pending-test",
            evaluated_at_us=0,
            through_sequence=1,
            status="pending",
            explanation_json="{}",
            next_due_at_us=due_at_us,
        )
        for case_id, due_at_us in [("due", 100), ("later", 101), ("resolved", 100)]
    }
    session.add_all(pending.values())
    session.flush()
    session.add(
        Assessment(
            case_id="resolved",
            evaluation_id="resolution",
            subject_speaker_id="A",
            model_id="harm_phrase",
            model_version="pending-test",
            evaluated_at_us=50,
            through_sequence=1,
            status="non-conformant",
            explanation_json="{}",
            resolves_assessment_id=pending["resolved"].assessment_id,
        )
    )
    session.commit()
    assert pending_cases(engine=engine, now_us=100) == ["changed", "due", "new"]
