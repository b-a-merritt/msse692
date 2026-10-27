"""Observation persistence, case-scoped identity, and value constraints."""

import pytest
from sqlalchemy import delete
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from normative_conformance import models


def test_observation_round_trip(*, session):
    session.add(models.ConversationCase(case_id="case", created_at_us=1))
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
    session.commit()
    session.expunge_all()

    stored = session.get(models.Observation, observation.observation_key)
    assert stored is not None
    assert stored.model_dump() == observation.model_dump()


@pytest.mark.parametrize(
    ("changes", "constraint"),
    [
        pytest.param({"observation_id": "chunk"}, "UNIQUE", id="duplicate-id"),
        pytest.param({"sequence": 1}, "UNIQUE", id="duplicate-sequence"),
        pytest.param({"case_id": "missing"}, "FOREIGN KEY", id="missing-case"),
        pytest.param({"sequence": 0}, "CHECK", id="nonpositive-sequence"),
        pytest.param({"sequence": None}, "CHECK", id="ingested-without-sequence"),
        pytest.param({"received_at_us": None}, "CHECK", id="ingested-without-receipt"),
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
    session.add(models.ConversationCase(case_id="case", created_at_us=1))
    session.flush()
    values = {
        "case_id": "case",
        "observation_id": "chunk",
        "sequence": 1,
        "received_at_us": 10,
        "speaker_id": "subject",
        "start_at_us": 1,
        "end_at_us": 9,
        "transcript": "Hello",
        "signal_level_min": -30.0,
        "signal_level_avg": -20.0,
        "signal_level_max": -10.0,
    }
    session.add(models.Observation(**values))
    session.commit()

    session.add(models.Observation(**(values | {"observation_id": "new", "sequence": 2} | changes)))
    with pytest.raises(IntegrityError, match=constraint):
        session.commit()


def test_observation_identity_is_scoped_to_case(*, session):
    session.add_all(
        [
            models.ConversationCase(case_id="case", created_at_us=1),
            models.ConversationCase(case_id="other", created_at_us=1),
        ]
    )
    session.flush()
    session.add_all(
        [
            models.Observation(
                case_id=case_id,
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
            for case_id in ("case", "other")
        ]
    )
    session.commit()

    assert session.exec(
        select(models.Observation.case_id).where(models.Observation.observation_id == "chunk")
    ).all() == ["case", "other"]


@pytest.mark.parametrize("level", [-120.0, 0.0])
def test_signal_boundaries_and_equal_levels_are_valid(*, session, level):
    session.add(models.ConversationCase(case_id="case", created_at_us=1))
    session.flush()
    observation = models.Observation(
        case_id="case",
        observation_id="boundary",
        sequence=1,
        received_at_us=10,
        speaker_id="subject",
        start_at_us=1,
        end_at_us=9,
        transcript="Hello",
        signal_level_min=level,
        signal_level_avg=level,
        signal_level_max=level,
    )
    session.add(observation)
    session.commit()
    session.expunge_all()
    assert session.get(models.Observation, observation.observation_key).signal_level_avg == level


@pytest.mark.parametrize(
    "statement",
    [
        pytest.param(update(models.Observation).values(speaker_id="B"), id="update"),
        pytest.param(delete(models.Observation), id="delete"),
    ],
)
def test_observations_are_append_only(session, statement):
    session.add(models.ConversationCase(case_id="case", created_at_us=0))
    session.flush()
    row = models.Observation(
        case_id="case",
        observation_id="old",
        sequence=1,
        received_at_us=10,
        speaker_id="A",
        start_at_us=1,
        end_at_us=9,
        transcript="Hello",
        signal_level_min=-50,
        signal_level_avg=-30,
        signal_level_max=-10,
    )
    session.add(row)
    session.commit()
    with pytest.raises(IntegrityError, match="observation is append-only"):
        session.execute(statement)
    session.rollback()
    session.expire_all()
    assert session.get(models.Observation, row.observation_key).speaker_id == "A"
