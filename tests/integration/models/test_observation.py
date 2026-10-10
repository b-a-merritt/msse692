"""Observation persistence, case-scoped identity, and value constraints."""

import pytest
from sqlalchemy.exc import IntegrityError

from normative_conformance import models


def test_observation_round_trip(*, session):
    case = models.CaseLog(case_id="case", created_at_us=1)
    session.add(case)
    session.flush()
    observation = models.Observation(
        case_id="case",
        observation_id="chunk",
        sequence=1,
        received_at_us=10,
        speaker_id="subject",
        start_at_us=1,
        end_at_us=9,
        transcript="Hello",
        signal_level_min=-30.0,
        signal_level_avg=-20.0,
        signal_level_max=-10.0,
    )
    session.add(observation)
    session.flush()
    session.commit()
    session.expunge_all()
    records = {"case": case, "observation": observation}

    original = records["observation"]
    stored = session.get(models.Observation, (original.case_id, original.observation_id))
    assert stored is not None
    assert stored.model_dump() == original.model_dump()


@pytest.mark.parametrize(
    ("changes", "constraint"),
    [
        pytest.param({"observation_id": "chunk"}, "UNIQUE", id="duplicate-id"),
        pytest.param({"sequence": 1}, "UNIQUE", id="duplicate-sequence"),
        pytest.param({"case_id": "missing"}, "FOREIGN KEY", id="missing-case"),
        pytest.param({"sequence": 0}, "CHECK", id="nonpositive-sequence"),
        pytest.param({"end_at_us": 1}, "CHECK", id="empty-interval"),
        pytest.param({"end_at_us": 0}, "CHECK", id="reversed-interval"),
        pytest.param({"signal_level_min": -121}, "CHECK", id="signal-below-range"),
        pytest.param({"signal_level_max": 1}, "CHECK", id="signal-above-range"),
        pytest.param({"signal_level_avg": -31}, "CHECK", id="average-below-minimum"),
        pytest.param({"signal_level_avg": -9}, "CHECK", id="average-above-maximum"),
        pytest.param({"received_at_us": "invalid"}, "cannot store TEXT", id="strict-type"),
        pytest.param({"transcript": None}, "NOT NULL", id="required-transcript"),
    ],
)
def test_invalid_observations_are_rejected(*, session, changes, constraint):
    case = models.CaseLog(case_id="case", created_at_us=1)
    session.add(case)
    session.flush()
    observation = models.Observation(
        case_id="case",
        observation_id="chunk",
        sequence=1,
        received_at_us=10,
        speaker_id="subject",
        start_at_us=1,
        end_at_us=9,
        transcript="Hello",
        signal_level_min=-30.0,
        signal_level_avg=-20.0,
        signal_level_max=-10.0,
    )
    session.add(observation)
    session.flush()
    session.commit()
    session.expunge_all()
    records = {"case": case, "observation": observation}

    values = records["observation"].model_dump()
    values.update(observation_id="new", sequence=2)
    values.update(changes)
    session.add(models.Observation(**values))
    with pytest.raises(IntegrityError, match=constraint):
        session.commit()


def test_observation_identity_is_scoped_to_case(*, session):
    case = models.CaseLog(case_id="case", created_at_us=1)
    session.add(case)
    session.flush()
    observation = models.Observation(
        case_id="case",
        observation_id="chunk",
        sequence=1,
        received_at_us=10,
        speaker_id="subject",
        start_at_us=1,
        end_at_us=9,
        transcript="Hello",
        signal_level_min=-30.0,
        signal_level_avg=-20.0,
        signal_level_max=-10.0,
    )
    session.add(observation)
    session.flush()
    session.commit()
    session.expunge_all()
    records = {"case": case, "observation": observation}

    session.add(models.CaseLog(case_id="other", created_at_us=1))
    session.flush()
    session.add(models.Observation(**(records["observation"].model_dump() | {"case_id": "other"})))
    session.commit()
    assert session.get(models.Observation, ("case", "chunk")) is not None
    assert session.get(models.Observation, ("other", "chunk")) is not None


@pytest.mark.parametrize("level", [-120.0, 0.0])
def test_signal_boundaries_and_equal_levels_are_valid(*, session, level):
    case = models.CaseLog(case_id="case", created_at_us=1)
    session.add(case)
    session.flush()
    observation = models.Observation(
        case_id="case",
        observation_id="chunk",
        sequence=1,
        received_at_us=10,
        speaker_id="subject",
        start_at_us=1,
        end_at_us=9,
        transcript="Hello",
        signal_level_min=-30.0,
        signal_level_avg=-20.0,
        signal_level_max=-10.0,
    )
    session.add(observation)
    session.flush()
    session.commit()
    session.expunge_all()
    records = {"case": case, "observation": observation}

    values = records["observation"].model_dump()
    values.update(
        observation_id="boundary",
        sequence=2,
        signal_level_min=level,
        signal_level_avg=level,
        signal_level_max=level,
    )
    session.add(models.Observation(**values))
    session.commit()
    assert session.get(models.Observation, ("case", "boundary")).signal_level_avg == level
