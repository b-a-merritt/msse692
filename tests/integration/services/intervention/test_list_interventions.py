from normative_conformance import models
from normative_conformance.services.intervention.list_interventions import list_interventions


def test_reads_stored_interventions_with_case_status_and_id_filters(*, session):
    session.add_all(
        models.CaseLog(case_id=case_id, created_at_us=0) for case_id in ("case", "other")
    )
    session.flush()
    session.add_all(
        [
            models.Observation(
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
            for case_id in ("case", "other")
        ]
    )
    session.add_all(
        [
            models.TargetAssignment(
                case_id=case_id, target_revision=revision, assigned_at_us=0, speaker_id=speaker
            )
            for case_id, revision, speaker in [
                ("case", 1, "former"),
                ("case", 2, "A"),
                ("other", 1, "A"),
            ]
        ]
    )
    session.flush()
    assessments = {
        name: models.Assessment(
            case_id=case_id,
            target_revision=revision,
            model_id="jev-1.14.0",
            prompt_version="conversation-1",
            evaluated_at_us=0,
            completed_at_us=0,
            after_sequence=0,
            through_sequence=1,
            action="intervene",
            action_confidence=0.9,
            selection_threshold=0.7,
            request_json="{}",
        )
        for name, case_id, revision in [
            ("first", "case", 2),
            ("second", "case", 2),
            ("other", "other", 1),
            ("stale", "case", 1),
        ]
    }
    session.add_all(assessments.values())
    session.flush()
    first = models.Intervention(
        assessment_id=assessments["first"].assessment_id,
        message="First",
        created_at_us=1,
        sent_at_us=2,
    )
    second = models.Intervention(
        assessment_id=assessments["second"].assessment_id, message="Second", created_at_us=3
    )
    other = models.Intervention(
        assessment_id=assessments["other"].assessment_id, message="Other", created_at_us=4
    )
    # An unsent intervention for a former target mapping is no longer pending.
    stale = models.Intervention(
        assessment_id=assessments["stale"].assessment_id, message="Stale", created_at_us=5
    )
    session.add_all([first, second, other, stale])
    session.commit()
    rows = {
        "first": (first, "case", "A"),
        "second": (second, "case", "A"),
        "other": (other, "other", "A"),
        "stale": (stale, "case", "former"),
    }

    assert list_interventions(session=session) == [
        rows["first"],
        rows["second"],
        rows["other"],
        rows["stale"],
    ]
    assert list_interventions(case_id="case", session=session) == [
        rows["first"],
        rows["second"],
        rows["stale"],
    ]
    assert list_interventions(case_id="missing", session=session) == []
    assert list_interventions(status="pending", session=session) == [rows["second"], rows["other"]]
    assert list_interventions(status="sent", session=session) == [rows["first"]]
    assert list_interventions(
        intervention_ids=[other.intervention_id, first.intervention_id], session=session
    ) == [rows["first"], rows["other"]]
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
