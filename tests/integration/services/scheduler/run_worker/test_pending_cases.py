from normative_conformance.models.case import CaseLog
from normative_conformance.models.case import TargetAssignment
from normative_conformance.models.observation import Observation
from normative_conformance.services.scheduler.run_worker.pending_cases import pending_cases


def test_only_resolved_cases_with_new_input_target_are_ready(engine, session):
    session.add_all(
        [
            CaseLog(case_id="new", created_at_us=0),
            CaseLog(case_id="unresolved", created_at_us=0),
            CaseLog(case_id="cleared", created_at_us=0),
            CaseLog(
                case_id="handled",
                created_at_us=0,
                last_handled_sequence=1,
                last_handled_target_revision=1,
            ),
            CaseLog(
                case_id="changed",
                created_at_us=0,
                last_handled_sequence=1,
                last_handled_target_revision=1,
            ),
            CaseLog(case_id="empty", created_at_us=0),
        ]
    )
    session.flush()
    session.add_all(
        [
            TargetAssignment(
                case_id=case_id, target_revision=revision, assigned_at_us=0, speaker_id=speaker
            )
            for case_id, revision, speaker in [
                ("new", 1, "A"),
                ("cleared", 1, "A"),
                ("cleared", 2, None),
                ("handled", 1, "A"),
                ("changed", 1, "A"),
                ("changed", 2, "B"),
                ("empty", 1, "A"),
            ]
        ]
    )
    session.add_all(
        [
            Observation(
                case_id=case_id,
                observation_id="one",
                sequence=1,
                received_at_us=0,
                start_at_us=0,
                end_at_us=1,
                speaker_id="A",
                transcript="hello",
                signal_level_min=-40,
                signal_level_avg=-30,
                signal_level_max=-20,
            )
            for case_id in ["new", "unresolved", "cleared", "handled", "changed"]
        ]
    )
    session.commit()
    assert pending_cases(engine=engine) == ["changed", "new"]
