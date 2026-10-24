import pytest

from normative_conformance.models.case import CaseLog
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


def test_recomputes_mapping_when_earlier_speaker_labels_change():
    case = CaseLog(
        case_id="case",
        created_at_us=0,
        target_speaker_order=2,
        target_speaker_id="B",
        target_revision=1,
    )
    refresh_target(case=case, labels=["B", "A"])
    assert case.target_speaker_id == "A"
    assert case.target_revision == 2
    refresh_target(case=case, labels=["B", "A", "A"])
    assert case.target_revision == 2
    refresh_target(case=case, labels=["B", "PENDING"])
    assert case.target_speaker_id is None
    assert case.target_revision == 3


def test_manual_selection_survives_remapping():
    case = CaseLog(
        case_id="case",
        created_at_us=0,
        target_speaker_order=2,
        target_speaker_id="B",
        target_speaker_manual=True,
        target_revision=4,
    )
    refresh_target(case=case, labels=["B", "A"])
    assert case.target_speaker_id == "B"
    assert case.target_revision == 4


def test_unconfigured_case_stays_unresolved():
    case = CaseLog(case_id="case", created_at_us=0)
    refresh_target(case=case, labels=["A", "B"])
    assert case.target_speaker_id is None
    assert case.target_revision == 0


def test_changing_back_to_previous_label_does_not_revalidate_old_work():
    case = CaseLog(case_id="case", created_at_us=0, target_speaker_id="A", target_revision=1)
    set_target_label(case=case, label="B")
    set_target_label(case=case, label="A")
    assert case.target_speaker_id == "A"
    assert case.target_revision == 3
