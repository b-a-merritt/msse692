from normative_conformance.models.case import CaseLog
from normative_conformance.models.observation import Observation
from normative_conformance.services.scheduler.run_worker.pending_cases import pending_cases


def test_only_resolved_cases_with_new_input_or_target_are_ready(engine, session):
    cases = [
        CaseLog(case_id="new", created_at_us=0, target_speaker_id="A"),
        CaseLog(case_id="unresolved", created_at_us=0),
        CaseLog(case_id="handled", created_at_us=0, target_speaker_id="A", last_handled_sequence=1),
        CaseLog(
            case_id="changed",
            created_at_us=0,
            target_speaker_id="B",
            last_handled_sequence=1,
            target_revision=2,
            last_handled_target_revision=1,
        ),
        CaseLog(case_id="empty", created_at_us=0, target_speaker_id="A", target_revision=1),
    ]
    session.add_all(cases)
    session.flush()
    for case_id in ["new", "unresolved", "handled", "changed"]:
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
    session.commit()
    assert pending_cases(engine=engine) == ["changed", "new"]
