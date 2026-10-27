"""Speaker revisions link replaced ingested speech to its corrected speech."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from normative_conformance import models


def test_revision_round_trip(session):
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.flush()
    original = models.Observation(
        case_id="case",
        observation_id="turn",
        sequence=1,
        received_at_us=1,
        speaker_id="A",
        start_at_us=0,
        end_at_us=10,
        transcript="Hello there",
        signal_level_min=-50,
        signal_level_avg=-30,
        signal_level_max=-10,
    )
    revision = models.SpeakerRevision(case_id="case", received_at_us=5)
    session.add_all([original, revision])
    session.flush()
    # A correction may reuse the ID of the speech it replaces.
    corrected = models.Observation(
        case_id="case",
        observation_id="turn",
        speaker_revision_id=revision.speaker_revision_id,
        speaker_id="B",
        start_at_us=0,
        end_at_us=10,
        transcript="Hello there",
        signal_level_min=-50,
        signal_level_avg=-30,
        signal_level_max=-10,
    )
    session.add_all(
        [
            corrected,
            models.ReplacedObservation(
                speaker_revision_id=revision.speaker_revision_id,
                observation_key=original.observation_key,
            ),
        ]
    )
    session.commit()
    session.expunge_all()

    assert session.exec(
        select(models.ReplacedObservation.observation_key, models.Observation.speaker_id).join(
            models.Observation,
            models.Observation.speaker_revision_id
            == models.ReplacedObservation.speaker_revision_id,
        )
    ).all() == [(original.observation_key, "B")]


def test_revision_requires_existing_case(session):
    session.add(models.SpeakerRevision(case_id="missing", received_at_us=5))
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        session.commit()


@pytest.mark.parametrize("replaced", ["other-case", "correction"])
def test_only_ingested_speech_in_the_revision_case_can_be_replaced(session, replaced):
    session.add_all(
        [
            models.CaseLog(case_id="case", created_at_us=0),
            models.CaseLog(case_id="other", created_at_us=0),
        ]
    )
    session.flush()
    revision = models.SpeakerRevision(case_id="case", received_at_us=5)
    session.add(revision)
    session.flush()
    candidates = {
        "other-case": models.Observation(
            case_id="other",
            observation_id="turn",
            sequence=1,
            received_at_us=1,
            speaker_id="A",
            start_at_us=0,
            end_at_us=10,
            transcript="Hello",
            signal_level_min=-50,
            signal_level_avg=-30,
            signal_level_max=-10,
        ),
        "correction": models.Observation(
            case_id="case",
            observation_id="turn",
            speaker_revision_id=revision.speaker_revision_id,
            speaker_id="B",
            start_at_us=0,
            end_at_us=10,
            transcript="Hello",
            signal_level_min=-50,
            signal_level_avg=-30,
            signal_level_max=-10,
        ),
    }
    session.add_all(candidates.values())
    session.commit()

    session.add(
        models.ReplacedObservation(
            speaker_revision_id=revision.speaker_revision_id,
            observation_key=candidates[replaced].observation_key,
        )
    )
    with pytest.raises(IntegrityError, match="replaces ingested observations in its case"):
        session.commit()


@pytest.mark.parametrize(
    "changes,reason",
    [
        pytest.param({"case_id": "other"}, "belong to its revision case", id="other-case"),
        pytest.param({"sequence": 1}, "CHECK", id="with-sequence"),
        pytest.param({"received_at_us": 1}, "CHECK", id="with-receipt"),
        pytest.param({"observation_id": "turn"}, "UNIQUE", id="duplicate-in-revision"),
    ],
)
def test_invalid_corrections_are_rejected(session, changes, reason):
    session.add_all(
        [
            models.CaseLog(case_id="case", created_at_us=0),
            models.CaseLog(case_id="other", created_at_us=0),
        ]
    )
    session.flush()
    revision = models.SpeakerRevision(case_id="case", received_at_us=5)
    session.add(revision)
    session.flush()
    values = {
        "case_id": "case",
        "observation_id": "turn",
        "speaker_revision_id": revision.speaker_revision_id,
        "speaker_id": "B",
        "start_at_us": 0,
        "end_at_us": 10,
        "transcript": "Hello",
        "signal_level_min": -50,
        "signal_level_avg": -30,
        "signal_level_max": -10,
    }
    session.add(models.Observation(**values))
    session.commit()

    session.add(models.Observation(**(values | {"observation_id": "new"} | changes)))
    with pytest.raises(IntegrityError, match=reason):
        session.commit()


@pytest.mark.parametrize("table", ["speaker_revision", "replaced_observation"])
@pytest.mark.parametrize("operation", ["update", "delete"])
def test_revisions_are_append_only(session, table, operation):
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.flush()
    original = models.Observation(
        case_id="case",
        observation_id="turn",
        sequence=1,
        received_at_us=1,
        speaker_id="A",
        start_at_us=0,
        end_at_us=10,
        transcript="Hello",
        signal_level_min=-50,
        signal_level_avg=-30,
        signal_level_max=-10,
    )
    revision = models.SpeakerRevision(case_id="case", received_at_us=5)
    session.add_all([original, revision])
    session.flush()
    replaced = models.ReplacedObservation(
        speaker_revision_id=revision.speaker_revision_id,
        observation_key=original.observation_key,
    )
    session.add(replaced)
    session.commit()

    row = revision if table == "speaker_revision" else replaced
    if operation == "delete":
        session.delete(row)
    elif table == "speaker_revision":
        revision.received_at_us = 6
    else:
        replaced.observation_key = original.observation_key + 1
    with pytest.raises(IntegrityError, match=f"{table} is append-only"):
        session.commit()
