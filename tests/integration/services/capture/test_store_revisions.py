import json
from datetime import datetime
from datetime import timezone
from pathlib import Path

import pytest
from sqlmodel import col
from sqlmodel import select

from normative_conformance.database import create_database_engine
from normative_conformance.database import read_session
from normative_conformance.database import write_session
from normative_conformance.errors import CaptureFailure
from normative_conformance.models.assessment import Assessment
from normative_conformance.models.case import CaseLog
from normative_conformance.models.normative_model import NormativeModelVersion
from normative_conformance.models.observation import Observation
from normative_conformance.models.speaker_revision import SpeakerRevision
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.schemas.observation import ObservationReplacement
from normative_conformance.services.capture.levels import FrameLevel
from normative_conformance.services.capture.observations import build_observations
from normative_conformance.services.capture.store_revisions import store_revisions
from normative_conformance.services.capture.transcriber import TurnUpdate
from normative_conformance.services.capture.transcriber import Word
from normative_conformance.services.observation.ingest import stage_observation
from normative_conformance.services.observation.records import to_record


def test_reopened_storage_can_supply_latest_corrected_context_without_capture_state(engine):
    start = datetime(2026, 10, 26, tzinfo=timezone.utc)
    frames = [
        FrameLevel(
            start_ms=offset,
            end_ms=offset + 20,
            dbfs=-60 if offset < 40 else -20 if offset < 100 else -30,
        )
        for offset in range(0, 240, 20)
    ]
    originals_by_turn = {}
    for turn in [
        TurnUpdate(
            0, True, "A", "Hello there", (Word("Hello", 0, 40, "A"), Word("there", 40, 100, "A"))
        ),
        TurnUpdate(
            1, True, "A", "Yes okay", (Word("Yes", 120, 160, "A"), Word("okay", 160, 200, "B"))
        ),
        TurnUpdate(2, True, "C", "Unchanged", (Word("Unchanged", 220, 240, "C"),)),
    ]:
        originals_by_turn[turn.turn_order] = build_observations(
            case_id="case", session_id="provider", started_at=start, frames=frames, turn=turn
        )
    case = CaseLog(case_id="case", created_at_us=0, target_speaker_order=1)
    model = NormativeModelVersion(
        model_id="test", version="1", name="Test model", rules_json="[]", parameters_json="{}"
    )
    with write_session(engine=engine) as session:
        session.add(case)
        session.add(model)
        session.flush()
        for rows in originals_by_turn.values():
            for row in rows:
                stage_observation(input=row, session=session, now=lambda: start)
        assessment = Assessment(
            assessment_id=1,
            evaluation_id="evaluated",
            case_id="case",
            subject_speaker_id="A",
            target_revision=case.target_revision,
            model_id="test",
            model_version="1",
            evaluated_at_us=2_000_000,
            through_sequence=4,
            status="conformant",
            explanation_json="{}",
        )
        session.add(assessment)
        session.commit()
    with read_session(engine=engine) as session:
        original_state = [
            row.model_dump()
            for row in session.exec(
                select(Observation)
                .where(Observation.case_id == "case")
                .order_by(Observation.sequence)
            ).all()
        ]
    case_state = case.model_dump()
    assessment_state = assessment.model_dump()

    # Turn 0 changes twice, ending in a split; turn 1 merges. Repeated revisions append.
    updates = [
        TurnUpdate(
            0, True, "B", "Hello there", (Word("Hello", 0, 40, "B"), Word("there", 40, 100, "B"))
        ),
        TurnUpdate(
            1, True, "B", "Yes okay", (Word("Yes", 120, 160, "B"), Word("okay", 160, 200, "B"))
        ),
        TurnUpdate(
            0, True, "A", "Hello there", (Word("Hello", 0, 40, "A"), Word("there", 40, 100, "B"))
        ),
        TurnUpdate(
            0, True, "A", "Hello there", (Word("Hello", 0, 40, "A"), Word("there", 40, 100, "B"))
        ),
    ]
    for turn in updates:
        store_revisions(
            case_id="case",
            replacements=[
                ObservationReplacement(
                    replaced_observation_ids=[
                        row.observation_id for row in originals_by_turn[turn.turn_order]
                    ],
                    observations=build_observations(
                        case_id="case",
                        session_id="provider",
                        started_at=start,
                        frames=frames,
                        turn=turn,
                    ),
                )
            ],
            engine=engine,
            now=lambda: datetime(2026, 10, 26, 0, 0, 5, tzinfo=timezone.utc),
        )

    database_path = Path(engine.url.database)
    engine.dispose()
    reopened = create_database_engine(path=database_path)
    try:
        with read_session(engine=reopened) as session:
            original_rows = session.exec(
                select(Observation)
                .where(Observation.case_id == "case")
                .order_by(Observation.sequence)
            ).all()
            revisions = session.exec(
                select(SpeakerRevision)
                .where(SpeakerRevision.case_id == "case")
                .order_by(col(SpeakerRevision.revision_id))
            ).all()
            assert len(revisions) == 4
            assert len({row.received_at_us for row in revisions}) == 1
            assert [row.model_dump() for row in original_rows] == original_state
            assert session.get(CaseLog, "case").model_dump() == case_state
            assert session.get(Assessment, 1).model_dump() == assessment_state
            assert len(session.exec(select(Assessment)).all()) == 1

            # Reconstruct solely from persisted data. Latest revision wins by revision_id.
            latest = {}
            for revision in revisions:
                original_ids = tuple(json.loads(revision.replaced_observation_ids_json))
                latest[original_ids] = [
                    ObservationInput.model_validate(value)
                    for value in json.loads(revision.observations_json)
                ]
            replaced_ids = {identity for identities in latest for identity in identities}
            context = [
                to_record(observation=row)
                for row in original_rows
                if row.observation_id not in replaced_ids
            ]
            context.extend(row for replacement in latest.values() for row in replacement)
            context.sort(key=lambda row: (row.start_at, row.end_at, row.observation_id))
            assert [(row.transcript, row.speaker_id) for row in context] == [
                ("Hello", "A"),
                ("there", "B"),
                ("Yes okay", "B"),
                ("Unchanged", "C"),
            ]
            assert [row.start_at.isoformat() for row in context] == [
                "2026-10-26T00:00:00+00:00",
                "2026-10-26T00:00:00.040000+00:00",
                "2026-10-26T00:00:00.120000+00:00",
                "2026-10-26T00:00:00.220000+00:00",
            ]
            assert context[2].end_at.isoformat() == "2026-10-26T00:00:00.200000+00:00"
            assert [row.signal_level_avg for row in context] == [-60, -20, -30, -30]
            assert len({row.observation_id for row in context}) == 4
            assert all(row.case_id == "case" for row in context)
    finally:
        reopened.dispose()


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
            CREATE TRIGGER reject_revision BEFORE INSERT ON speaker_revision
            WHEN json_extract(NEW.replaced_observation_ids_json, '$[0]') = 'two'
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
        assert len(session.exec(select(Observation)).all()) == 2
