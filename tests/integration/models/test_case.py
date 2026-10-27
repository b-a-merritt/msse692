"""Case selection and target history survive storage and obey database constraints."""

import pytest
from sqlalchemy import delete
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from normative_conformance.models.case import ConversationCase
from normative_conformance.models.case import TargetAssignment


def test_case_and_target_assignment_round_trip(session):
    case = ConversationCase(
        case_id="case",
        created_at_us=1,
        target_speaker_order=2,
        last_handled_sequence=4,
        last_handled_target_revision=3,
    )
    assignment = TargetAssignment(
        case_id="case", target_revision=3, assigned_at_us=2, speaker_id="B"
    )
    session.add(case)
    session.flush()
    session.add(assignment)
    session.commit()
    session.expunge_all()
    assert session.get(ConversationCase, "case").model_dump() == case.model_dump()
    assert session.get(TargetAssignment, ("case", 3)).model_dump() == assignment.model_dump()


def test_database_rejects_invalid_speaking_order(session):
    session.add(ConversationCase(case_id="case", created_at_us=0, target_speaker_order=3))
    with pytest.raises(IntegrityError, match="CHECK"):
        session.commit()


@pytest.mark.parametrize(
    "changes,reason",
    [
        pytest.param({"case_id": "missing"}, "FOREIGN KEY", id="missing-case"),
        pytest.param({"target_revision": 0}, "CHECK", id="revision-zero"),
        pytest.param({"speaker_id": "PENDING"}, "CHECK", id="pending-label"),
        pytest.param({"speaker_id": " "}, "CHECK", id="blank-label"),
    ],
)
def test_database_rejects_invalid_target_assignment(session, changes, reason):
    session.add(ConversationCase(case_id="case", created_at_us=0))
    session.commit()
    values = {"case_id": "case", "target_revision": 1, "assigned_at_us": 0, "speaker_id": "A"}
    session.add(TargetAssignment(**(values | changes)))
    with pytest.raises(IntegrityError, match=reason):
        session.commit()


@pytest.mark.parametrize(
    "statement",
    [
        pytest.param(update(TargetAssignment).values(speaker_id="B"), id="update"),
        pytest.param(delete(TargetAssignment), id="delete"),
    ],
)
def test_target_assignments_are_append_only(session, statement):
    session.add(ConversationCase(case_id="case", created_at_us=0))
    session.flush()
    assignment = TargetAssignment(
        case_id="case", target_revision=1, assigned_at_us=0, speaker_id="A"
    )
    session.add(assignment)
    session.commit()
    with pytest.raises(IntegrityError, match="target_assignment is append-only"):
        session.execute(statement)
