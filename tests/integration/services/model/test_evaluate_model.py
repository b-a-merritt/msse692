from itertools import count

import pytest

from normative_conformance import models
from normative_conformance.services.model.evaluate_model import evaluate_model
from normative_conformance.services.model.get_model import get_model
from normative_conformance.services.model.get_subject_speaker_id import get_subject_speaker_id
from normative_conformance.services.observation.get_case_sequence import get_case_sequence

from ...storage import persist


def test_interruption_counts_distinct_entries_in_captured_prefix(*, session):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)

    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="other",
            start_at_us=0,
            end_at_us=10_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="another",
            start_at_us=500_000,
            end_at_us=10_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    for start in [1, 4, 7]:
        persist(
            session=session,
            record=models.Observation(
                case_id="case",
                observation_id=str(observation_sequence := next(observation_sequences)),
                sequence=observation_sequence,
                speaker_id="configured-subject",
                start_at_us=round((start) * 1_000_000),
                end_at_us=round((start + 0.3) * 1_000_000),
                received_at_us=0,
                transcript="hello",
                signal_level_min=-60.0,
                signal_level_avg=-50.0,
                signal_level_max=0.0,
            ),
        )
    assert not evaluate_model(
        model=get_model(model_id="repeated_interruption", version="1", session=session),
        case_id="case",
        subject_speaker_id=get_subject_speaker_id(session=session),
        through_sequence=3,
        session=session,
        after_observation=None,
        deadline_at_us=None,
    )
    assert evaluate_model(
        model=get_model(model_id="repeated_interruption", version="1", session=session),
        case_id="case",
        subject_speaker_id=get_subject_speaker_id(session=session),
        through_sequence=get_case_sequence(case_id="case", session=session),
        session=session,
        after_observation=None,
        deadline_at_us=None,
    )


@pytest.mark.parametrize("overlap,expected", [(0.15, True), (0.149999, False)])
def test_interruption_requires_minimum_overlap(*, session, overlap, expected):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)

    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="other",
            start_at_us=0,
            end_at_us=10_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    for start in [1, 4]:
        persist(
            session=session,
            record=models.Observation(
                case_id="case",
                observation_id=str(observation_sequence := next(observation_sequences)),
                sequence=observation_sequence,
                speaker_id="configured-subject",
                start_at_us=round((start) * 1_000_000),
                end_at_us=round((start + overlap) * 1_000_000),
                received_at_us=0,
                transcript="hello",
                signal_level_min=-60.0,
                signal_level_avg=-30.0,
                signal_level_max=0.0,
            ),
        )
    assert (
        evaluate_model(
            model=get_model(model_id="repeated_interruption", version="1", session=session),
            case_id="case",
            subject_speaker_id=get_subject_speaker_id(session=session),
            through_sequence=get_case_sequence(case_id="case", session=session),
            session=session,
            after_observation=None,
            deadline_at_us=None,
        )
        is expected
    )


def test_continuous_speech_does_not_manufacture_interruptions(*, session):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)

    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="other",
            start_at_us=0,
            end_at_us=10_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    for start in [1, 2, 3]:
        persist(
            session=session,
            record=models.Observation(
                case_id="case",
                observation_id=str(observation_sequence := next(observation_sequences)),
                sequence=observation_sequence,
                speaker_id="configured-subject",
                start_at_us=round((start) * 1_000_000),
                end_at_us=round((start + 1) * 1_000_000),
                received_at_us=0,
                transcript="hello",
                signal_level_min=-60.0,
                signal_level_avg=-30.0,
                signal_level_max=0.0,
            ),
        )
    assert not evaluate_model(
        model=get_model(model_id="repeated_interruption", version="1", session=session),
        case_id="case",
        subject_speaker_id=get_subject_speaker_id(session=session),
        through_sequence=get_case_sequence(case_id="case", session=session),
        session=session,
        after_observation=None,
        deadline_at_us=None,
    )


@pytest.mark.parametrize(
    "level,end,expected",
    [(-17.0, 0.9, True), (-18.0, 0.9, False), (-17.0, 1.0, False)],
)
def test_address_requires_loud_fast_speech(*, session, level, end, expected):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)

    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=round((end) * 1_000_000),
            received_at_us=0,
            transcript="stop that now",
            signal_level_min=-60.0,
            signal_level_avg=level,
            signal_level_max=0.0,
        ),
    )
    assert (
        evaluate_model(
            model=get_model(model_id="high_intensity_address", version="1", session=session),
            case_id="case",
            subject_speaker_id=get_subject_speaker_id(session=session),
            through_sequence=get_case_sequence(case_id="case", session=session),
            session=session,
            after_observation=None,
            deadline_at_us=None,
        )
        is expected
    )


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
def test_character_label_matches_quiet_slow_speech(*, session, transcript, expected):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)

    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=5_000_000,
            received_at_us=0,
            transcript=transcript,
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    assert (
        evaluate_model(
            model=get_model(model_id="character_label", version="1", session=session),
            case_id="case",
            subject_speaker_id=get_subject_speaker_id(session=session),
            through_sequence=get_case_sequence(case_id="case", session=session),
            session=session,
            after_observation=None,
            deadline_at_us=None,
        )
        is expected
    )


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
def test_vulgar_language_matches_term_variants(*, session, transcript, expected):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)

    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=5_000_000,
            received_at_us=0,
            transcript=transcript,
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    assert (
        evaluate_model(
            model=get_model(model_id="vulgar_language", version="1", session=session),
            case_id="case",
            subject_speaker_id=get_subject_speaker_id(session=session),
            through_sequence=get_case_sequence(case_id="case", session=session),
            session=session,
            after_observation=None,
            deadline_at_us=None,
        )
        is expected
    )


@pytest.mark.parametrize(
    "transcript,expected",
    [
        ("Every day I wake up and I hope you're dead.", True),
        ("Do this and I swear to God—", True),
        ("I hope you're doing well", False),
    ],
)
def test_harm_phrase_matches_configured_phrases(*, session, transcript, expected):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)

    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=5_000_000,
            received_at_us=0,
            transcript=transcript,
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    assert (
        evaluate_model(
            model=get_model(model_id="harm_phrase", version="1", session=session),
            case_id="case",
            subject_speaker_id=get_subject_speaker_id(session=session),
            through_sequence=get_case_sequence(case_id="case", session=session),
            session=session,
            after_observation=None,
            deadline_at_us=None,
        )
        is expected
    )


@pytest.mark.parametrize(
    "transcript,expected",
    [
        ("You always made me aware of what I was doing wrong", True),
        ("You'll never be happy.", True),
        ("I never cheated on you.", False),
    ],
)
def test_absolutist_phrase_requires_second_person(*, session, transcript, expected):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)

    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=5_000_000,
            received_at_us=0,
            transcript=transcript,
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    assert (
        evaluate_model(
            model=get_model(model_id="absolutist_phrase", version="1", session=session),
            case_id="case",
            subject_speaker_id=get_subject_speaker_id(session=session),
            through_sequence=get_case_sequence(case_id="case", session=session),
            session=session,
            after_observation=None,
            deadline_at_us=None,
        )
        is expected
    )


def test_subject_comes_from_experiment_config(*, session):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)

    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="subject",
            start_at_us=0,
            end_at_us=900_000,
            received_at_us=0,
            transcript="you are a liar",
            signal_level_min=-60.0,
            signal_level_avg=-17.0,
            signal_level_max=0.0,
        ),
    )
    assert not evaluate_model(
        model=get_model(model_id="high_intensity_address", version="1", session=session),
        case_id="case",
        subject_speaker_id=get_subject_speaker_id(session=session),
        through_sequence=get_case_sequence(case_id="case", session=session),
        session=session,
        after_observation=None,
        deadline_at_us=None,
    )


def test_extended_turn_threshold_and_gap(*, session):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)

    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=15_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=16_000_000,
            end_at_us=30_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    assert not evaluate_model(
        model=get_model(model_id="extended_turn", version="1", session=session),
        case_id="case",
        subject_speaker_id=get_subject_speaker_id(session=session),
        through_sequence=get_case_sequence(case_id="case", session=session),
        session=session,
        after_observation=None,
        deadline_at_us=None,
    )
    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=31_000_000,
            end_at_us=31_000_001,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    assert evaluate_model(
        model=get_model(model_id="extended_turn", version="1", session=session),
        case_id="case",
        subject_speaker_id=get_subject_speaker_id(session=session),
        through_sequence=get_case_sequence(case_id="case", session=session),
        session=session,
        after_observation=None,
        deadline_at_us=None,
    )


def test_other_speaker_breaks_turn_in_gap(*, session):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)

    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=15_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="other",
            start_at_us=15_500_000,
            end_at_us=15_800_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=16_000_000,
            end_at_us=32_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    assert not evaluate_model(
        model=get_model(model_id="extended_turn", version="1", session=session),
        case_id="case",
        subject_speaker_id=get_subject_speaker_id(session=session),
        through_sequence=get_case_sequence(case_id="case", session=session),
        session=session,
        after_observation=None,
        deadline_at_us=None,
    )


@pytest.mark.parametrize("received,expected", [(9.999999, True), (10, False)])
def test_repair_rule_uses_supplied_source_and_receipt_bounds(*, session, received, expected):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)

    activation = persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=1_000_000,
            end_at_us=2_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=3_000_000,
            end_at_us=4_000_000,
            received_at_us=round((received) * 1_000_000),
            transcript="I AM, SORRY!",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    assert (
        evaluate_model(
            model=get_model(model_id="apology", version="1", session=session),
            case_id="case",
            subject_speaker_id=get_subject_speaker_id(session=session),
            through_sequence=get_case_sequence(case_id="case", session=session),
            session=session,
            after_observation=activation,
            deadline_at_us=10_000_000,
        )
        is expected
    )


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
def test_repair_models_match_configured_phrases(*, session, model_id, transcript, expected):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)

    activation = persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=1_000_000,
            end_at_us=2_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=3_000_000,
            end_at_us=4_000_000,
            received_at_us=0,
            transcript=transcript,
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    assert (
        evaluate_model(
            model=get_model(model_id=model_id, version="1", session=session),
            case_id="case",
            subject_speaker_id=get_subject_speaker_id(session=session),
            through_sequence=get_case_sequence(case_id="case", session=session),
            session=session,
            after_observation=activation,
            deadline_at_us=None,
        )
        is expected
    )


def test_earlier_spoken_apology_does_not_repair_later_behavior(*, session):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)

    activation = persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=3_000_000,
            end_at_us=4_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=1_000_000,
            end_at_us=2_000_000,
            received_at_us=2_000_000,
            transcript="I apologize",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    assert not evaluate_model(
        model=get_model(model_id="apology", version="1", session=session),
        case_id="case",
        subject_speaker_id=get_subject_speaker_id(session=session),
        through_sequence=get_case_sequence(case_id="case", session=session),
        session=session,
        after_observation=activation,
        deadline_at_us=10_000_000,
    )
