from normative_conformance import models
from normative_conformance.schemas.observation import ObservationRecord
from normative_conformance.services.observation.list_observations import list_observations
from normative_conformance.timestamps import from_microseconds


def test_returns_observations_newest_first_with_converted_timestamps(*, add_observation, session):
    first = add_observation(start=0, end=1, received=10)
    second = add_observation(start=2, end=3, received=20)

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


def test_only_returns_observations_for_the_requested_case(*, add_observation, session):
    add_observation(start=0, end=1)
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
