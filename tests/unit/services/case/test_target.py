from unittest.mock import Mock

import pytest
from sqlmodel import Session

from normative_conformance.models.case import TargetAssignment
from normative_conformance.services.case import target
from normative_conformance.services.case.target import refresh_target
from normative_conformance.services.case.target import resolve_speaker_order
from normative_conformance.services.case.target import set_target_label


@pytest.mark.parametrize(
    "labels,order,expected",
    [
        (["A", "A", "B"], 2, "B"),
        (["Z", "Z", "Q"], 1, "Z"),
        ([None, "", " ", "PENDING", "A", "A", "B"], 2, "B"),
        (["PENDING", "A", "A"], 2, None),
        ([], 1, None),
    ],
)
def test_resolves_distinct_speakers_without_assuming_letters(labels, order, expected):
    assert resolve_speaker_order(labels=labels, order=order) == expected


@pytest.mark.parametrize("order", [0, 3])
def test_rejects_unsupported_order(order):
    with pytest.raises(ValueError, match="1 or 2"):
        resolve_speaker_order(labels=["A", "B"], order=order)


def test_recomputes_mapping_when_earlier_speaker_labels_change(monkeypatch):
    assignments = [
        TargetAssignment(case_id="case", target_revision=1, assigned_at_us=0, speaker_id="B")
    ]
    session = Mock(spec=Session)
    session.add.side_effect = assignments.append
    monkeypatch.setattr(target, "current_assignment", lambda **kwargs: assignments[-1])
    refresh_target(
        case_id="case", target_speaker_order=2, labels=["B", "A"], session=session, assigned_at_us=5
    )
    refresh_target(
        case_id="case",
        target_speaker_order=2,
        labels=["B", "A", "A"],
        session=session,
        assigned_at_us=6,
    )
    refresh_target(
        case_id="case",
        target_speaker_order=2,
        labels=["B", "PENDING"],
        session=session,
        assigned_at_us=7,
    )

    assert [(row.target_revision, row.assigned_at_us, row.speaker_id) for row in assignments] == [
        (1, 0, "B"),
        (2, 5, "A"),
        (3, 7, None),
    ]


def test_case_without_speaking_order_keeps_its_target(monkeypatch):
    session = Mock(spec=Session)
    monkeypatch.setattr(target, "current_assignment", Mock())
    refresh_target(
        case_id="case",
        target_speaker_order=None,
        labels=["A", "B"],
        session=session,
        assigned_at_us=5,
    )

    session.add.assert_not_called()


def test_first_label_starts_at_revision_one_and_no_label_needs_no_assignment(monkeypatch):
    assignments = []
    session = Mock(spec=Session)
    session.add.side_effect = assignments.append
    monkeypatch.setattr(
        target, "current_assignment", lambda **kwargs: assignments[-1] if assignments else None
    )

    set_target_label(case_id="case", label=None, session=session, assigned_at_us=1)
    set_target_label(case_id="case", label="A", session=session, assigned_at_us=2)

    assert [(row.case_id, row.target_revision, row.speaker_id) for row in assignments] == [
        ("case", 1, "A")
    ]


def test_changing_back_to_previous_label_does_not_revalidate_old_work(monkeypatch):
    assignments = [
        TargetAssignment(case_id="case", target_revision=1, assigned_at_us=0, speaker_id="A")
    ]
    session = Mock(spec=Session)
    session.add.side_effect = assignments.append
    monkeypatch.setattr(target, "current_assignment", lambda **kwargs: assignments[-1])

    set_target_label(case_id="case", label="B", session=session, assigned_at_us=1)
    set_target_label(case_id="case", label="A", session=session, assigned_at_us=2)

    assert [(row.target_revision, row.speaker_id) for row in assignments] == [
        (1, "A"),
        (2, "B"),
        (3, "A"),
    ]
