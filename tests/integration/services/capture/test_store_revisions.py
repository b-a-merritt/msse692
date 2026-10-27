from datetime import datetime
from datetime import timezone

import pytest
from sqlmodel import select

from normative_conformance.database import read_session
from normative_conformance.database import write_session
from normative_conformance.errors import CaptureFailure
from normative_conformance.models.case import CaseLog
from normative_conformance.models.observation import Observation
from normative_conformance.models.speaker_revision import ReplacedObservation
from normative_conformance.models.speaker_revision import SpeakerRevision
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.schemas.observation import ObservationReplacement
from normative_conformance.services.capture.store_revisions import store_revisions
from normative_conformance.services.observation.ingest import stage_observation


def test_revisions_link_replaced_speech_to_corrected_speech(engine):
    with write_session(engine=engine) as session:
        session.add(CaseLog(case_id="case", created_at_us=0))
        session.commit()
        for identity, start, end in [
            ("one", "1970-01-01T00:00:00Z", "1970-01-01T00:00:01Z"),
            ("two", "1970-01-01T00:00:01Z", "1970-01-01T00:00:02Z"),
        ]:
            stage_observation(
                input=ObservationInput(
                    case_id="case",
                    observation_id=identity,
                    speaker_id="A",
                    start_at=start,
                    end_at=end,
                    transcript="Hello",
                    signal_level_min=-30,
                    signal_level_avg=-30,
                    signal_level_max=-30,
                ),
                session=session,
                now=lambda: datetime(1970, 1, 1, tzinfo=timezone.utc),
            )
        session.commit()

    store_revisions(
        case_id="case",
        replacements=[
            ObservationReplacement(
                replaced_observation_ids=["one", "two"],
                observations=[
                    ObservationInput(
                        case_id="case",
                        observation_id="one",
                        speaker_id="B",
                        start_at="1970-01-01T00:00:00Z",
                        end_at="1970-01-01T00:00:02Z",
                        transcript="Hello Hello",
                        signal_level_min=-30,
                        signal_level_avg=-30,
                        signal_level_max=-30,
                    )
                ],
            )
        ],
        engine=engine,
        now=lambda: datetime(1970, 1, 1, 0, 0, 5, tzinfo=timezone.utc),
    )

    with read_session(engine=engine) as session:
        revision = session.exec(select(SpeakerRevision)).one()
        assert (revision.case_id, revision.received_at_us) == ("case", 5_000_000)
        replaced = session.exec(
            select(Observation.observation_id)
            .join(ReplacedObservation)
            .where(ReplacedObservation.speaker_revision_id == revision.speaker_revision_id)
            .order_by(Observation.observation_id)
        ).all()
        assert replaced == ["one", "two"]
        rows = session.exec(select(Observation).order_by(Observation.observation_key)).all()
        assert [
            (row.observation_id, row.speaker_id, row.sequence, row.speaker_revision_id)
            for row in rows
        ] == [
            ("one", "A", 1, None),
            ("two", "A", 2, None),
            ("one", "B", None, revision.speaker_revision_id),
        ]


def test_second_replacement_failure_rolls_back_batch(engine):
    with write_session(engine=engine) as session:
        session.add(CaseLog(case_id="case", created_at_us=0))
        session.commit()
        for identity, label, start, end in [
            ("one", "A", "1970-01-01T00:00:00Z", "1970-01-01T00:00:01Z"),
            ("two", "B", "1970-01-01T00:00:01Z", "1970-01-01T00:00:02Z"),
        ]:
            stage_observation(
                input=ObservationInput(
                    case_id="case",
                    observation_id=identity,
                    speaker_id=label,
                    start_at=start,
                    end_at=end,
                    transcript="Hello",
                    signal_level_min=-30,
                    signal_level_avg=-30,
                    signal_level_max=-30,
                ),
                session=session,
                now=lambda: datetime(1970, 1, 1, tzinfo=timezone.utc),
            )
        session.commit()
    with engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE TRIGGER reject_revision BEFORE INSERT ON observation
            WHEN NEW.speaker_revision_id IS NOT NULL AND NEW.observation_id = 'two'
            BEGIN SELECT RAISE(ABORT, 'cannot write'); END
        """)
    replacements = [
        ObservationReplacement(
            replaced_observation_ids=[identity],
            observations=[
                ObservationInput(
                    case_id="case",
                    observation_id=identity,
                    speaker_id="B",
                    start_at=start,
                    end_at=end,
                    transcript="Hello",
                    signal_level_min=-30,
                    signal_level_avg=-30,
                    signal_level_max=-30,
                )
            ],
        )
        for identity, start, end in [
            ("one", "1970-01-01T00:00:00Z", "1970-01-01T00:00:01Z"),
            ("two", "1970-01-01T00:00:01Z", "1970-01-01T00:00:02Z"),
        ]
    ]
    with pytest.raises(CaptureFailure) as caught:
        store_revisions(
            case_id="case",
            replacements=replacements,
            engine=engine,
            now=lambda: datetime(1970, 1, 1, tzinfo=timezone.utc),
        )
    assert caught.value.code == "storageUnavailable"
    with read_session(engine=engine) as session:
        assert session.exec(select(SpeakerRevision)).all() == []
        assert session.exec(select(ReplacedObservation)).all() == []
        assert len(session.exec(select(Observation)).all()) == 2
