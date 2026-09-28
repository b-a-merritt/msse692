from datetime import datetime
from datetime import timezone

from normative_conformance.services.assessment.list_assessment_records import (
    list_assessment_records,
)


def test_no_assessments_returns_empty_records_without_experiment_configuration(*, session):
    assert list_assessment_records(case_id="missing", session=session) == []


def test_records_preserve_each_assessments_prefix_explanation_and_deadline(
    *, session, add_observation, assess, check
):
    first = add_observation(start=0, end=31)
    pending = assess(at=100)[0]
    second = add_observation(start=32, end=33)
    resolution = check(at=110)[0]
    add_observation(start=34, end=35)

    records = list_assessment_records(case_id="case", session=session)

    assert [record.assessment_id for record in records] == [
        pending.assessment_id,
        resolution.assessment_id,
    ]
    assert [record.resolves_assessment_id for record in records] == [None, pending.assessment_id]
    assert [record.extent.observation_ids for record in records] == [
        [first.observation_id],
        [first.observation_id, second.observation_id],
    ]
    assert [record.extent.through_sequence for record in records] == [1, 2]
    assert [record.extent.observation_count for record in records] == [1, 2]
    assert [record.status for record in records] == ["pending", "conformant"]
    assert [record.explanation.reason_code for record in records] == ["awaiting_repair", "matched"]
    assert [record.evaluated_at for record in records] == [
        datetime.fromtimestamp(100, timezone.utc),
        datetime.fromtimestamp(110, timezone.utc),
    ]
    assert [record.next_due_at for record in records] == [
        datetime.fromtimestamp(110, timezone.utc),
        None,
    ]
    assert {record.subject_speaker_id for record in records} == {"configured-subject"}
