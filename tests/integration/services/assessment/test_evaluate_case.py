from datetime import datetime
from datetime import timezone
from itertools import count
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select

from normative_conformance import models
from normative_conformance.database import read_session
from normative_conformance.database import write_session
from normative_conformance.models.assessment import Assessment
from normative_conformance.models.normative_model import NormativeModelVersion
from normative_conformance.schemas.assessment import Explanation
from normative_conformance.services.assessment.check_repairs import check_repairs
from normative_conformance.services.assessment.evaluate_case import evaluate_case
from normative_conformance.services.model.list_models import list_models

from ...storage import persist


def test_detection_time_starts_deadline_and_new_matches_do_not_restart_it(*, session, engine):
    session.add(
        models.CaseLog(target_speaker_id="configured-subject", case_id="case", created_at_us=0)
    )
    session.commit()
    observation_sequences = count(1)

    persist(
        session=session,
        record=models.Observation(
            updated_at_us=0,
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=1_500_000,
            received_at_us=0,
            transcript="stop that right now please",
            signal_level_min=-60.0,
            signal_level_avg=-16.0,
            signal_level_max=0.0,
        ),
    )
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    with write_session(engine=engine) as assessment_session:
        first = evaluate_case(
            case_id="case",
            evaluation_id=uuid4(),
            session=assessment_session,
            now=lambda: datetime.fromtimestamp(100, timezone.utc),
            models=evaluation_models,
        )
        assessment_session.commit()
    session.commit()
    assert len(first) == 1
    assert first[0].status == "pending"
    assert first[0].evaluated_at_us == 100_000_000
    assert first[0].next_due_at_us == 110_000_000
    explanation = Explanation.model_validate_json(first[0].explanation_json)
    assert explanation.reason_code == "awaiting_repair"
    assert explanation.rules[0].outcome == "pending"
    assert explanation.rules[0].deadline_at.timestamp() == 110
    persist(
        session=session,
        record=models.Observation(
            updated_at_us=109_000_000,
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=1_000_000,
            end_at_us=2_500_000,
            received_at_us=109_000_000,
            transcript="stop it right now please",
            signal_level_min=-60.0,
            signal_level_avg=-16.0,
            signal_level_max=0.0,
        ),
    )
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    with write_session(engine=engine) as assessment_session:
        again = evaluate_case(
            case_id="case",
            evaluation_id=uuid4(),
            session=assessment_session,
            now=lambda: datetime.fromtimestamp(109, timezone.utc),
            models=evaluation_models,
        )
        assessment_session.commit()
    session.commit()
    assert [row.model_dump() for row in again] == [row.model_dump() for row in first]
    assert len(session.exec(select(Assessment)).all()) == 1


def test_no_match_creates_no_pending_assessment(*, session, engine):
    session.add(
        models.CaseLog(target_speaker_id="configured-subject", case_id="case", created_at_us=0)
    )
    session.commit()
    observation_sequences = count(1)

    persist(
        session=session,
        record=models.Observation(
            updated_at_us=0,
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
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    with write_session(engine=engine) as assessment_session:
        assert (
            evaluate_case(
                case_id="case",
                evaluation_id=uuid4(),
                session=assessment_session,
                now=lambda: datetime.fromtimestamp(100, timezone.utc),
                models=evaluation_models,
            )
            == []
        )
        assessment_session.commit()


def test_no_repair_allowance_confirms_immediately(*, session, engine):
    session.add(
        models.CaseLog(target_speaker_id="configured-subject", case_id="case", created_at_us=0)
    )
    session.commit()
    observation_sequences = count(1)

    persist(
        session=session,
        record=models.Observation(
            updated_at_us=0,
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
    session.add(
        NormativeModelVersion(
            model_id="immediate",
            version="1",
            name="Immediate",
            type="undesired",
            repair_allowance_us=None,
            rules_json='[{"rule_id":"always","description":"Always matches","sql":"SELECT 1"}]',
            parameters_json="{}",
        )
    )
    session.commit()
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    with write_session(engine=engine) as assessment_session:
        result = evaluate_case(
            case_id="case",
            evaluation_id=uuid4(),
            session=assessment_session,
            now=lambda: datetime.fromtimestamp(100, timezone.utc),
            models=evaluation_models,
        )
        assessment_session.commit()
    session.commit()
    assert len(result) == 1
    assert result[0].status == "conformant"
    assert result[0].next_due_at_us is None
    explanation = Explanation.model_validate_json(result[0].explanation_json)
    assert explanation.reason_code == "matched"
    assert explanation.rules[0].outcome == "satisfied"
    assert explanation.rules[0].deadline_at is None

    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    with write_session(engine=engine) as assessment_session:
        repeated = evaluate_case(
            case_id="case",
            evaluation_id=uuid4(),
            session=assessment_session,
            now=lambda: datetime.fromtimestamp(101, timezone.utc),
            models=evaluation_models,
        )
        assessment_session.commit()
    session.commit()
    assert [row.assessment_id for row in repeated] == [result[0].assessment_id]
    assert len(session.exec(select(Assessment)).all()) == 1


def test_models_use_their_own_allowance_and_keep_existing_deadlines(*, session, engine):
    session.add(
        models.CaseLog(target_speaker_id="configured-subject", case_id="case", created_at_us=0)
    )
    session.commit()
    observation_sequences = count(1)

    persist(
        session=session,
        record=models.Observation(
            updated_at_us=0,
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
    for model_id, allowance in [("short", 2_000_000), ("long", 20_000_000)]:
        session.add(
            NormativeModelVersion(
                model_id=model_id,
                version="1",
                name=model_id,
                type="undesired",
                repair_allowance_us=allowance,
                rules_json='[{"rule_id":"always","description":"Always matches","sql":"SELECT 1"}]',
                parameters_json="{}",
            )
        )
    session.commit()

    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    with write_session(engine=engine) as assessment_session:
        originals = {
            row.model_id: row
            for row in evaluate_case(
                case_id="case",
                evaluation_id=uuid4(),
                session=assessment_session,
                now=lambda: datetime.fromtimestamp(100, timezone.utc),
                models=evaluation_models,
            )
        }
        assessment_session.commit()

    assert originals["short"].next_due_at_us == 102_000_000
    assert originals["long"].next_due_at_us == 120_000_000
    for row in originals.values():
        assert row.status == "pending"
        explanation = Explanation.model_validate_json(row.explanation_json)
        assert explanation.rules[0].deadline_at.timestamp() * 1_000_000 == row.next_due_at_us
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    with write_session(engine=engine) as assessment_session:
        assert [
            row.model_dump()
            for row in evaluate_case(
                case_id="case",
                evaluation_id=uuid4(),
                session=assessment_session,
                now=lambda: datetime.fromtimestamp(101, timezone.utc),
                models=evaluation_models,
            )
        ] == [row.model_dump() for row in originals.values()]
        assessment_session.commit()

    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    with write_session(engine=engine) as assessment_session:
        checked = {
            row.model_id: row
            for row in check_repairs(
                case_id="case",
                evaluation_id=uuid4(),
                session=assessment_session,
                now=lambda: datetime.fromtimestamp(102, timezone.utc),
                models=evaluation_models,
            )
        }
        assessment_session.commit()
    assert checked["short"].status == "conformant"
    assert checked["short"].resolves_assessment_id == originals["short"].assessment_id
    assert checked["long"].model_dump() == originals["long"].model_dump()


def test_failed_assessment_rolls_back_all_models(*, session, engine):
    session.add(
        models.CaseLog(target_speaker_id="configured-subject", case_id="case", created_at_us=0)
    )
    session.commit()
    observation_sequences = count(1)

    persist(
        session=session,
        record=models.Observation(
            updated_at_us=0,
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=1_500_000,
            received_at_us=0,
            transcript="stop that right now please",
            signal_level_min=-60.0,
            signal_level_avg=-16.0,
            signal_level_max=0.0,
        ),
    )
    persist(
        session=session,
        record=models.Observation(
            updated_at_us=0,
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=1_000_000,
            end_at_us=32_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    # Extended turn is stored first; fail the second model's write.
    with engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE TRIGGER fail_assessment BEFORE INSERT ON assessment
            WHEN NEW.model_id = 'high_intensity_address'
            BEGIN SELECT RAISE(ABORT, 'Assessment write failed'); END
        """)

    with pytest.raises(SQLAlchemyError):
        with read_session(engine=engine) as catalog_session:
            evaluation_models = list_models(session=catalog_session)
        with write_session(engine=engine) as assessment_session:
            evaluate_case(
                case_id="case",
                evaluation_id=uuid4(),
                session=assessment_session,
                now=lambda: datetime.fromtimestamp(100, timezone.utc),
                models=evaluation_models,
            )
            assessment_session.commit()
        session.commit()

    with read_session(engine=engine) as session:
        assert session.exec(select(Assessment)).all() == []


def test_new_matches_share_the_case_evaluation_time(*, session, engine):
    session.add(
        models.CaseLog(target_speaker_id="configured-subject", case_id="case", created_at_us=0)
    )
    session.commit()
    observation_sequences = count(1)
    with read_session(engine=engine) as catalog_session:
        model_catalog = list_models(session=catalog_session)

    persist(
        session=session,
        record=models.Observation(
            updated_at_us=0,
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=1_500_000,
            received_at_us=0,
            transcript="stop that right now please",
            signal_level_min=-60.0,
            signal_level_avg=-16.0,
            signal_level_max=0.0,
        ),
    )
    persist(
        session=session,
        record=models.Observation(
            updated_at_us=0,
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=1_000_000,
            end_at_us=32_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    times = iter([100])

    with write_session(engine=engine) as assessment_session:
        results = evaluate_case(
            case_id="case",
            evaluation_id=uuid4(),
            session=assessment_session,
            now=lambda: datetime.fromtimestamp(next(times), timezone.utc),
            models=model_catalog,
        )
        assessment_session.commit()
    session.commit()

    assert [(row.model_id, row.evaluated_at_us, row.next_due_at_us) for row in results] == [
        ("extended_turn", 100_000_000, 110_000_000),
        ("high_intensity_address", 100_000_000, 110_000_000),
    ]


def test_models_record_the_same_case_target(*, session, engine):
    session.add(
        models.CaseLog(target_speaker_id="configured-subject", case_id="case", created_at_us=0)
    )
    session.commit()
    observation_sequences = count(1)

    persist(
        session=session,
        record=models.Observation(
            updated_at_us=0,
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=0,
            end_at_us=1_500_000,
            received_at_us=0,
            transcript="stop that right now please",
            signal_level_min=-60.0,
            signal_level_avg=-16.0,
            signal_level_max=0.0,
        ),
    )
    persist(
        session=session,
        record=models.Observation(
            updated_at_us=0,
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=1_000_000,
            end_at_us=32_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )

    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    with write_session(engine=engine) as assessment_session:
        results = evaluate_case(
            case_id="case",
            evaluation_id=uuid4(),
            session=assessment_session,
            now=lambda: datetime.fromtimestamp(100, timezone.utc),
            models=evaluation_models,
        )
        assessment_session.commit()
    session.commit()
    assert len(results) == 2
    assert {row.subject_speaker_id for row in results} == {"configured-subject"}
    assert {row.target_revision for row in results} == {0}


def test_model_added_after_the_catalog_was_loaded_is_not_assessed(*, session, engine):
    session.add(
        models.CaseLog(target_speaker_id="configured-subject", case_id="case", created_at_us=0)
    )
    session.commit()
    observation_sequences = count(1)
    with read_session(engine=engine) as catalog_session:
        model_catalog = list_models(session=catalog_session)
    received_at = datetime(2026, 9, 26, 9, 2, 3, 456_789, tzinfo=timezone.utc)

    persist(
        session=session,
        record=models.Observation(
            updated_at_us=0,
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
    session.add(
        NormativeModelVersion(
            model_id="late",
            version="1",
            name="Late",
            type="undesired",
            repair_allowance_us=None,
            rules_json='[{"rule_id":"always","description":"Always matches","sql":"SELECT 1"}]',
            parameters_json="{}",
        )
    )
    session.commit()

    with write_session(engine=engine) as assessment_session:
        results = evaluate_case(
            case_id="case",
            evaluation_id=uuid4(),
            session=assessment_session,
            now=lambda: received_at,
            models=model_catalog,
        )
        assessment_session.commit()
    session.commit()

    assert results == []
