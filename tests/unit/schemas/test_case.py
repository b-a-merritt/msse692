import pytest
from pydantic import ValidationError

from normative_conformance.schemas.case import TargetSelection


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"target_speaker_order": 1, "target_speaker_id": "A"},
        {"target_speaker_order": 0},
        {"target_speaker_order": 3},
        {"target_speaker_order": True},
        {"target_speaker_order": "2"},
        {"target_speaker_id": ""},
        {"target_speaker_id": " "},
        {"target_speaker_id": "PENDING"},
        {"target_speaker_id": "a/b"},
        {"target_speaker_id": 1},
        {"extra": "A"},
    ],
)
def test_selection_requires_exactly_one_valid_input(values):
    with pytest.raises(ValidationError):
        TargetSelection(**values)


@pytest.mark.parametrize(
    "values",
    [
        {"target_speaker_order": 1},
        {"target_speaker_order": 2},
        {"target_speaker_id": "speaker-2"},
        {"target_speaker_id": "Q"},
    ],
)
def test_accepts_order_or_a_known_replay_label(values):
    assert TargetSelection(**values).model_dump(exclude_none=True) == values
