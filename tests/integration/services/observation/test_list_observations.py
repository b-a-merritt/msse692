from itertools import count

from normative_conformance import models
from normative_conformance.schemas.observation import ObservationRecord
from normative_conformance.services.observation.list_observations import list_observations
from normative_conformance.timestamps import from_microseconds

from ...storage import persist


def test_returns_observations_newest_first_with_converted_timestamps(*, session):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)

    first = persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=1_000_000,
            received_at_us=10_000_000,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    second = persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=2_000_000,
            end_at_us=3_000_000,
            received_at_us=20_000_000,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )

    records = list_observations(case_id="case", session=session)

    assert all(isinstance(record, ObservationRecord) for record in records)
    assert [record.observation_id for record in records] == [
        second.observation_id,
        first.observation_id,
    ]
    newest = records[0]
    assert newest.case_id == "case"
    assert newest.speaker_id == "configured-subject"
    assert newest.transcript == "hello"
    assert (newest.signal_level_min, newest.signal_level_avg, newest.signal_level_max) == (
        -60.0,
        -30.0,
        0.0,
    )
    assert newest.sequence == second.sequence
    assert newest.start_at == from_microseconds(value=second.start_at_us)
    assert newest.end_at == from_microseconds(value=second.end_at_us)
    assert newest.received_at == from_microseconds(value=second.received_at_us)


def test_only_returns_observations_for_the_requested_case(*, session):
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
            end_at_us=1_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    session.add(models.CaseLog(case_id="other", created_at_us=0))
    session.add(
        models.Observation(
            case_id="other",
            observation_id="other-chunk",
            sequence=1,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=1_000_000,
            received_at_us=0,
            transcript="elsewhere",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        )
    )
    session.commit()

    records = list_observations(case_id="other", session=session)

    assert [record.observation_id for record in records] == ["other-chunk"]


def test_unknown_case_returns_an_empty_list(*, session):
    assert list_observations(case_id="missing-case", session=session) == []
