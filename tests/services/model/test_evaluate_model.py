import pytest


def test_interruption_counts_distinct_entries_in_captured_prefix(*, add_observation, matches):
    add_observation(start=0, end=10, speaker="other")
    add_observation(start=0.5, end=10, speaker="another")
    for start in [1, 4, 7]:
        add_observation(start=start, end=start + 0.3, level=-50.0)
    assert not matches(model_id="repeated_interruption", through_sequence=3)
    assert matches(model_id="repeated_interruption")


@pytest.mark.parametrize("overlap,expected", [(0.15, True), (0.149999, False)])
def test_interruption_requires_minimum_overlap(*, add_observation, matches, overlap, expected):
    add_observation(start=0, end=10, speaker="other")
    for start in [1, 4]:
        add_observation(start=start, end=start + overlap)
    assert matches(model_id="repeated_interruption") is expected


def test_continuous_speech_does_not_manufacture_interruptions(*, add_observation, matches):
    add_observation(start=0, end=10, speaker="other")
    for start in [1, 2, 3]:
        add_observation(start=start, end=start + 1)
    assert not matches(model_id="repeated_interruption")


@pytest.mark.parametrize(
    "level,end,expected",
    [(-17.0, 0.9, True), (-18.0, 0.9, False), (-17.0, 1.0, False)],
)
def test_address_requires_loud_fast_speech(*, add_observation, matches, level, end, expected):
    add_observation(start=0, end=end, transcript="stop that now", level=level)
    assert matches(model_id="high_intensity_address") is expected


@pytest.mark.parametrize(
    "transcript,expected",
    [
        ("YOU'RE A, liar!", True),
        ("You're exactly like your mother.", True),
        ("You sound like your father", True),
        ("It's pathetic.", True),
        ("You're such a selfish bitch", True),
        ("you are being a dick", True),
        ("You're a great dad", False),
        ("You're fucking kidding me", False),
        ("oh, FUCKING hell", False),
        ("you are wrong", False),
    ],
)
def test_character_label_matches_quiet_slow_speech(
    *, add_observation, matches, transcript, expected
):
    add_observation(start=0, end=5, transcript=transcript)
    assert matches(model_id="character_label") is expected


@pytest.mark.parametrize(
    "transcript,expected",
    [
        ("Fuck.", True),
        ("oh, FUCKING hell", True),
        ("what a shitty day", True),
        ("some sort of goddamn punishment", True),
        ("You're a great dad", False),
        ("Dickens wrote that", False),
        ("He shot the scrapbook", False),
    ],
)
def test_vulgar_language_matches_term_variants(*, add_observation, matches, transcript, expected):
    add_observation(start=0, end=5, transcript=transcript)
    assert matches(model_id="vulgar_language") is expected


@pytest.mark.parametrize(
    "transcript,expected",
    [
        ("Every day I wake up and I hope you're dead.", True),
        ("Do this and I swear to God—", True),
        ("I hope you're doing well", False),
    ],
)
def test_harm_phrase_matches_configured_phrases(*, add_observation, matches, transcript, expected):
    add_observation(start=0, end=5, transcript=transcript)
    assert matches(model_id="harm_phrase") is expected


@pytest.mark.parametrize(
    "transcript,expected",
    [
        ("You always made me aware of what I was doing wrong", True),
        ("You'll never be happy.", True),
        ("I never cheated on you.", False),
    ],
)
def test_absolutist_phrase_requires_second_person(
    *, add_observation, matches, transcript, expected
):
    add_observation(start=0, end=5, transcript=transcript)
    assert matches(model_id="absolutist_phrase") is expected


def test_subject_comes_from_experiment_config(*, add_observation, matches):
    add_observation(start=0, end=0.9, transcript="you are a liar", level=-17.0, speaker="subject")
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


@pytest.mark.parametrize(
    "model_id,transcript,expected",
    [
        ("apology", "I'm sorry.", True),
        ("agreement_phrase", "Okay, you're right.", True),
        ("agreement_phrase", "No, you're damn right I am.", False),
        ("intent_disclaimer", "I didn't mean it like that", True),
        ("intent_disclaimer", "I did not mean to", True),
    ],
)
def test_repair_models_match_configured_phrases(
    *,
    add_observation,
    matches,
    model_id,
    transcript,
    expected,
):
    activation = add_observation(start=1, end=2)
    add_observation(start=3, end=4, transcript=transcript)
    assert matches(model_id=model_id, after=activation) is expected


def test_earlier_spoken_apology_does_not_repair_later_behavior(*, add_observation, matches):
    activation = add_observation(start=3, end=4)
    add_observation(start=1, end=2, transcript="I apologize", received=2)
    assert not matches(model_id="apology", after=activation, deadline=10_000_000)
