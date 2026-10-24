"""Case selection survives storage and obeys database constraints."""

import pytest
from sqlalchemy.exc import IntegrityError

from normative_conformance.models.case import CaseLog


def test_case_target_round_trip(session):
    case = CaseLog(
        case_id="case",
        created_at_us=1,
        target_speaker_order=2,
        target_speaker_id="B",
        target_speaker_manual=True,
        target_revision=3,
    )
    session.add(case)
    session.commit()
    session.expunge_all()
    stored = session.get(CaseLog, "case")
    assert stored is not None
    assert stored.model_dump() == case.model_dump()


@pytest.mark.parametrize(
    "values",
    [
        {"target_speaker_order": 3},
        {"target_speaker_id": "PENDING"},
        {"target_speaker_manual": True},
        {"target_revision": -1},
    ],
)
def test_database_rejects_invalid_target_state(session, values):
    session.add(CaseLog(case_id="case", created_at_us=0, **values))
    with pytest.raises(IntegrityError):
        session.commit()
