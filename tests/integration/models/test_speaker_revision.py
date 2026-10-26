import pytest
from sqlalchemy.exc import IntegrityError

from normative_conformance.models.case import CaseLog
from normative_conformance.models.speaker_revision import SpeakerRevision


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_revisions_are_append_only(session, operation):
    session.add(CaseLog(case_id="case", created_at_us=0))
    session.flush()
    row = SpeakerRevision(
        case_id="case",
        received_at_us=5,
        replaced_observation_ids_json='["original"]',
        observations_json="[]",
    )
    session.add(row)
    session.commit()
    revision_id = row.revision_id
    if operation == "update":
        row.observations_json = '[{"speaker_id":"A"}]'
    else:
        session.delete(row)
    with pytest.raises(IntegrityError, match="speaker revision is append-only"):
        session.commit()
    session.rollback()
    session.expire_all()
    stored = session.get(SpeakerRevision, revision_id)
    assert stored is not None
    assert stored.observations_json == "[]"
    assert stored.replaced_observation_ids_json == '["original"]'
    assert stored.received_at_us == 5


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"case_id": "missing"}, "FOREIGN KEY"),
        ({"observations_json": "not json"}, "CHECK"),
        ({"observations_json": "{}"}, "CHECK"),
        ({"replaced_observation_ids_json": "not json"}, "CHECK"),
        ({"replaced_observation_ids_json": "{}"}, "CHECK"),
    ],
)
def test_revision_constraints(session, changes, reason):
    session.add(CaseLog(case_id="case", created_at_us=0))
    session.commit()
    values = {
        "case_id": "case",
        "received_at_us": 5,
        "replaced_observation_ids_json": '["original"]',
        "observations_json": "[]",
    }
    session.add(SpeakerRevision(**(values | changes)))
    with pytest.raises(IntegrityError, match=reason):
        session.commit()
