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
from normative_conformance.schemas.assessment import CaseSnapshot
from normative_conformance.services.assessment.check_repairs import check_repairs
from normative_conformance.services.assessment.evaluate_case import evaluate_case
from normative_conformance.services.model.list_models import list_models
from normative_conformance.services.observation.get_case_sequence import get_case_sequence
from normative_conformance.timestamps import to_microseconds

from ...storage import persist


def test_repair_can_resolve_multiple_pending_models(*, session, engine):
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
        pending = evaluate_case(
            snapshot=CaseSnapshot(
                case_id="case",
                evaluation_id=str(uuid4()),
                through_sequence=get_case_sequence(case_id="case", session=assessment_session),
                evaluated_at_us=100_000_000,
            ),
            subject_speaker_id="configured-subject",
            session=assessment_session,
            models=evaluation_models,
        )
        assessment_session.commit()
    session.commit()
    assert len(pending) == 2
    persist(
        session=session,
        record=models.Observation(
            updated_at_us=105_000_000,
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=33_000_000,
            end_at_us=34_000_000,
            received_at_us=105_000_000,
            transcript="I am sorry",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    with write_session(engine=engine) as assessment_session:
        resolutions = [
            row
            for row in check_repairs(
                snapshot=CaseSnapshot(
                    case_id="case",
                    evaluation_id=str(uuid4()),
                    through_sequence=get_case_sequence(case_id="case", session=assessment_session),
                    evaluated_at_us=105_000_000,
                ),
                subject_speaker_id="configured-subject",
                session=assessment_session,
                models=evaluation_models,
            )
            if row.resolves_assessment_id is not None
        ]
        assessment_session.commit()
    assert {row.resolves_assessment_id for row in resolutions} == {
        row.assessment_id for row in pending
    }
    assert all(row.status == "non-conformant" for row in resolutions)


def test_repair_and_resolution_records_preserve_the_case_target(*, session, engine):
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
        evaluate_case(
            snapshot=CaseSnapshot(
                case_id="case",
                evaluation_id=str(uuid4()),
                through_sequence=get_case_sequence(case_id="case", session=assessment_session),
                evaluated_at_us=100_000_000,
            ),
            subject_speaker_id="configured-subject",
            session=assessment_session,
            models=evaluation_models,
        )
        assessment_session.commit()
    session.commit()
    persist(
        session=session,
        record=models.Observation(
            updated_at_us=105_000_000,
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=33_000_000,
            end_at_us=34_000_000,
            received_at_us=105_000_000,
            transcript="I apologize",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )

    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    with write_session(engine=engine) as assessment_session:
        results = check_repairs(
            snapshot=CaseSnapshot(
                case_id="case",
                evaluation_id=str(uuid4()),
                through_sequence=get_case_sequence(case_id="case", session=assessment_session),
                evaluated_at_us=105_000_000,
            ),
            subject_speaker_id="configured-subject",
            session=assessment_session,
            models=evaluation_models,
        )
        assessment_session.commit()
    session.commit()

    assert len(results) == 3
    assert {row.subject_speaker_id for row in results} == {"configured-subject"}
    assert {row.target_revision for row in results} == {0}


def test_late_repair_resets_future_detection_without_retracting_positive(*, session, engine):
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
        evaluate_case(
            snapshot=CaseSnapshot(
                case_id="case",
                evaluation_id=str(uuid4()),
                through_sequence=get_case_sequence(case_id="case", session=assessment_session),
                evaluated_at_us=100_000_000,
            ),
            subject_speaker_id="configured-subject",
            session=assessment_session,
            models=evaluation_models,
        )
        assessment_session.commit()
    session.commit()
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    with write_session(engine=engine) as assessment_session:
        final = check_repairs(
            snapshot=CaseSnapshot(
                case_id="case",
                evaluation_id=str(uuid4()),
                through_sequence=get_case_sequence(case_id="case", session=assessment_session),
                evaluated_at_us=110_000_000,
            ),
            subject_speaker_id="configured-subject",
            session=assessment_session,
            models=evaluation_models,
        )[0]
        assessment_session.commit()
    before = final.model_dump()
    persist(
        session=session,
        record=models.Observation(
            updated_at_us=111_000_000,
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=1_000_000,
            end_at_us=2_000_000,
            received_at_us=111_000_000,
            transcript="I apologize",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    with write_session(engine=engine) as assessment_session:
        check_repairs(
            snapshot=CaseSnapshot(
                case_id="case",
                evaluation_id=str(uuid4()),
                through_sequence=get_case_sequence(case_id="case", session=assessment_session),
                evaluated_at_us=111_000_000,
            ),
            subject_speaker_id="configured-subject",
            session=assessment_session,
            models=evaluation_models,
        )
        assessment_session.commit()
    session.commit()
    persist(
        session=session,
        record=models.Observation(
            updated_at_us=112_000_000,
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=3_000_000,
            end_at_us=4_500_000,
            received_at_us=112_000_000,
            transcript="stop that right now please",
            signal_level_min=-60.0,
            signal_level_avg=-16.0,
            signal_level_max=0.0,
        ),
    )
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    with write_session(engine=engine) as assessment_session:
        new = evaluate_case(
            snapshot=CaseSnapshot(
                case_id="case",
                evaluation_id=str(uuid4()),
                through_sequence=get_case_sequence(case_id="case", session=assessment_session),
                evaluated_at_us=112_000_000,
            ),
            subject_speaker_id="configured-subject",
            session=assessment_session,
            models=evaluation_models,
        )[0]
        assessment_session.commit()
    assert new.status == "pending"
    assert new.next_due_at_us == 122_000_000
    assert session.get(Assessment, final.assessment_id).model_dump() == before


def test_repair_resets_incomplete_interruption_pattern(*, session, engine):
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
            speaker_id="other",
            start_at_us=0,
            end_at_us=20_000_000,
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
            updated_at_us=0,
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
            updated_at_us=0,
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
            updated_at_us=0,
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=5_000_000,
            end_at_us=6_000_000,
            received_at_us=0,
            transcript="I apologize",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
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
            start_at_us=7_000_000,
            end_at_us=8_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    # Detection submits a candidate; the separate repair check removes the old evidence.
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    with write_session(engine=engine) as assessment_session:
        evaluate_case(
            snapshot=CaseSnapshot(
                case_id="case",
                evaluation_id=str(uuid4()),
                through_sequence=get_case_sequence(case_id="case", session=assessment_session),
                evaluated_at_us=100_000_000,
            ),
            subject_speaker_id="configured-subject",
            session=assessment_session,
            models=evaluation_models,
        )
        assessment_session.commit()
    session.commit()
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    with write_session(engine=engine) as assessment_session:
        check_repairs(
            snapshot=CaseSnapshot(
                case_id="case",
                evaluation_id=str(uuid4()),
                through_sequence=get_case_sequence(case_id="case", session=assessment_session),
                evaluated_at_us=100_000_000,
            ),
            subject_speaker_id="configured-subject",
            session=assessment_session,
            models=evaluation_models,
        )
        assessment_session.commit()
    session.commit()
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    with write_session(engine=engine) as assessment_session:
        assert (
            evaluate_case(
                snapshot=CaseSnapshot(
                    case_id="case",
                    evaluation_id=str(uuid4()),
                    through_sequence=get_case_sequence(case_id="case", session=assessment_session),
                    evaluated_at_us=101_000_000,
                ),
                subject_speaker_id="configured-subject",
                session=assessment_session,
                models=evaluation_models,
            )
            == []
        )
        assessment_session.commit()


def test_repeated_checks_append_only_one_resolution(*, session, engine):
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
            end_at_us=31_000_000,
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
        evaluate_case(
            snapshot=CaseSnapshot(
                case_id="case",
                evaluation_id=str(uuid4()),
                through_sequence=get_case_sequence(case_id="case", session=assessment_session),
                evaluated_at_us=100_000_000,
            ),
            subject_speaker_id="configured-subject",
            session=assessment_session,
            models=evaluation_models,
        )
        assessment_session.commit()
    session.commit()
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    with write_session(engine=engine) as assessment_session:
        first = check_repairs(
            snapshot=CaseSnapshot(
                case_id="case",
                evaluation_id=str(uuid4()),
                through_sequence=get_case_sequence(case_id="case", session=assessment_session),
                evaluated_at_us=110_000_000,
            ),
            subject_speaker_id="configured-subject",
            session=assessment_session,
            models=evaluation_models,
        )
        assessment_session.commit()
    session.commit()
    assert len(first) == 1
    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    with write_session(engine=engine) as assessment_session:
        assert (
            check_repairs(
                snapshot=CaseSnapshot(
                    case_id="case",
                    evaluation_id=str(uuid4()),
                    through_sequence=get_case_sequence(case_id="case", session=assessment_session),
                    evaluated_at_us=111_000_000,
                ),
                subject_speaker_id="configured-subject",
                session=assessment_session,
                models=evaluation_models,
            )
            == []
        )
        assessment_session.commit()
    assert len(session.exec(select(Assessment)).all()) == 2


@pytest.mark.parametrize("at", [105, 110])
def test_check_without_repair_resolves_only_due_matches(*, session, engine, at):
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
        evaluate_case(
            snapshot=CaseSnapshot(
                case_id="case",
                evaluation_id=str(uuid4()),
                through_sequence=get_case_sequence(case_id="case", session=assessment_session),
                evaluated_at_us=100_000_000,
            ),
            subject_speaker_id="configured-subject",
            session=assessment_session,
            models=evaluation_models,
        )
        assessment_session.commit()
    session.commit()

    with read_session(engine=engine) as catalog_session:
        evaluation_models = list_models(session=catalog_session)
    with write_session(engine=engine) as assessment_session:
        results = check_repairs(
            snapshot=CaseSnapshot(
                case_id="case",
                evaluation_id=str(uuid4()),
                through_sequence=get_case_sequence(case_id="case", session=assessment_session),
                evaluated_at_us=to_microseconds(value=datetime.fromtimestamp(at, timezone.utc)),
            ),
            subject_speaker_id="configured-subject",
            session=assessment_session,
            models=evaluation_models,
        )
        assessment_session.commit()
    session.commit()

    assert results[0].status == ("pending" if at < 110 else "conformant")


def test_failed_resolution_rolls_back_repair(*, session, engine):
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
        original = evaluate_case(
            snapshot=CaseSnapshot(
                case_id="case",
                evaluation_id=str(uuid4()),
                through_sequence=get_case_sequence(case_id="case", session=assessment_session),
                evaluated_at_us=100_000_000,
            ),
            subject_speaker_id="configured-subject",
            session=assessment_session,
            models=evaluation_models,
        )[0]
        assessment_session.commit()
    persist(
        session=session,
        record=models.Observation(
            updated_at_us=105_000_000,
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=1_000_000,
            end_at_us=2_000_000,
            received_at_us=105_000_000,
            transcript="I apologize",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    # The apology is stored first; a failed resolution must roll it back too.
    with engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE TRIGGER fail_resolution BEFORE INSERT ON assessment
            WHEN NEW.resolves_assessment_id IS NOT NULL
            BEGIN SELECT RAISE(ABORT, 'Resolution write failed'); END
        """)

    with pytest.raises(SQLAlchemyError):
        with read_session(engine=engine) as catalog_session:
            evaluation_models = list_models(session=catalog_session)
        with write_session(engine=engine) as assessment_session:
            check_repairs(
                snapshot=CaseSnapshot(
                    case_id="case",
                    evaluation_id=str(uuid4()),
                    through_sequence=get_case_sequence(case_id="case", session=assessment_session),
                    evaluated_at_us=105_000_000,
                ),
                subject_speaker_id="configured-subject",
                session=assessment_session,
                models=evaluation_models,
            )
            assessment_session.commit()
        session.commit()

    with read_session(engine=engine) as session:
        rows = session.exec(select(Assessment)).all()
        assert [row.model_dump() for row in rows] == [original.model_dump()]
