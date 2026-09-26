import pytest


def test_interruption_counts_distinct_entries_in_captured_prefix(*, add_observation, matches):
    add_observation(start=0, end=10, speaker="other")
    add_observation(start=0.5, end=10, speaker="another")
    for start in [1, 4, 7]:
        add_observation(start=start, end=start + 0.3, level=-50.0)
    assert not matches(model_id="repeated_interruption", through_sequence=4)
    assert matches(model_id="repeated_interruption")


def test_continuous_speech_does_not_manufacture_interruptions(*, add_observation, matches):
    add_observation(start=0, end=10, speaker="other")
    for start in [1, 2, 3]:
        add_observation(start=start, end=start + 1)
    assert not matches(model_id="repeated_interruption")


@pytest.mark.parametrize(
    "transcript,level,end,expected",
    [
        ("YOU, are WRONG!", -17.0, 0.9, True),
        ("you are ridiculous", -17.0, 0.9, True),
        ("you are wrongheaded", -17.0, 0.9, False),
        ("you are wrong", -18.0, 0.9, False),
        ("you are wrong", -17.0, 1.0, False),
    ],
)
def test_address_conditions_apply_to_same_chunk(
    *,
    add_observation,
    matches,
    transcript,
    level,
    end,
    expected,
):
    add_observation(start=0, end=end, transcript=transcript, level=level)
    assert matches(model_id="high_intensity_address") is expected


def test_subject_comes_from_experiment_config(*, add_observation, matches):
    add_observation(start=0, end=0.9, transcript="you are wrong", level=-17.0, speaker="subject")
    assert not matches(model_id="high_intensity_address")


def test_extended_turn_threshold_and_gap(*, add_observation, matches):
    add_observation(start=0, end=15)
    add_observation(start=16, end=30)
    assert not matches(model_id="extended_turn")
    add_observation(start=31, end=31.000001)
    assert matches(model_id="extended_turn")


def test_other_speaker_breaks_turn_in_gap(*, add_observation, matches):
    add_observation(start=0, end=15)
    add_observation(start=15.5, end=15.8, speaker="other")
    add_observation(start=16, end=32)
    assert not matches(model_id="extended_turn")


@pytest.mark.parametrize("received,expected", [(9.999999, True), (10, False)])
def test_repair_rule_uses_supplied_source_and_receipt_bounds(
    *,
    add_observation,
    matches,
    received,
    expected,
):
    activation = add_observation(start=1, end=2)
    add_observation(start=3, end=4, transcript="I AM, SORRY!", received=received)
    assert matches(model_id="apology", after=activation, deadline=10_000_000) is expected


def test_earlier_spoken_apology_does_not_repair_later_behavior(*, add_observation, matches):
    activation = add_observation(start=3, end=4)
    add_observation(start=1, end=2, transcript="I apologize", received=2)
    assert not matches(model_id="apology", after=activation, deadline=10_000_000)
