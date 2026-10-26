from datetime import datetime
from datetime import timezone

from sqlmodel import col
from sqlmodel import select

from normative_conformance.database import read_session
from normative_conformance.database import write_session
from normative_conformance.models.assessment import Assessment
from normative_conformance.models.case import CaseLog
from normative_conformance.models.normative_model import NormativeModelVersion
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.case import TargetSelection
from normative_conformance.schemas.model import ModelVersion
from normative_conformance.services.assessment.list_assessment_records import (
    list_assessment_records,
)
from normative_conformance.services.case.selection import select_target
from normative_conformance.services.intervention.create_intervention import create_intervention
from normative_conformance.services.intervention.deliver_pending import deliver_pending
from normative_conformance.services.intervention.list_intervention_records import (
    list_intervention_records,
)
from normative_conformance.services.scheduler.run_worker.process_case import process_case


def test_target_changes_invalidate_stored_work_without_relabeling_history(engine):
    def now():
        return datetime(1970, 1, 1, 0, 0, 1, tzinfo=timezone.utc)

    # The model and speech relevant to this storage test are defined here, not in a seed fixture.
    model = ModelVersion(
        model_id="harm_phrase",
        version="target-test",
        name="Target test",
        type="undesired",
        parameters={},
        rules=[
            {
                "rule_id": "speaker",
                "description": "Match the selected speaker",
                "sql": "SELECT 1 FROM observation WHERE case_id = :case_id "
                "AND speaker_id = :subject_speaker_id "
                "AND sequence <= :through_sequence",
            }
        ],
    )
    with write_session(engine=engine) as session:
        session.add(CaseLog(case_id="case", created_at_us=0))
        session.add(
            NormativeModelVersion(
                model_id=model.model_id,
                version=model.version,
                name=model.name,
                type=model.type,
                parameters_json="{}",
                rules_json='[{"rule_id":"speaker","description":"Match the selected speaker",'
                '"sql":"SELECT 1 FROM observation WHERE case_id = :case_id '
                "AND speaker_id = :subject_speaker_id "
                'AND sequence <= :through_sequence"}]',
            )
        )
        session.flush()
        session.add(
            Observation(
                updated_at_us=10,
                case_id="case",
                observation_id="first",
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
        )
        session.commit()
    assert process_case(case_id="case", engine=engine, now=now, models=[model]) is None
    with read_session(engine=engine) as session:
        assert _assessments(session=session) == []
    with write_session(engine=engine) as session:
        select_target(
            case_id="case",
            selection=TargetSelection(target_speaker_id="A"),
            session=session,
            now=now,
        )
    process_case(case_id="case", engine=engine, now=now, models=[model])
    with read_session(engine=engine) as session:
        first = _assessments(session=session)
    assert len(first) == 1
    assert first[0].target_revision == 1
    with write_session(engine=engine) as session:
        create_intervention(case_id="case", since_us=0, session=session, now=now)
    with write_session(engine=engine) as session:
        select_target(
            case_id="case",
            selection=TargetSelection(target_speaker_id="B"),
            session=session,
            now=now,
        )
    with write_session(engine=engine) as session:
        assert deliver_pending(case_id="case", session=session, now=now) == []
    with read_session(engine=engine) as session:
        assert list_intervention_records(case_id="case", status="pending", session=session) == []
        assert [
            row.subject_speaker_id
            for row in list_assessment_records(case_id="case", session=session)
        ] == ["A"]
        assert [
            row.subject_speaker_id
            for row in list_intervention_records(case_id="case", session=session)
        ] == ["A"]
    process_case(case_id="case", engine=engine, now=now, models=[model])
    with read_session(engine=engine) as session:
        assert _assessments(session=session) == first
    # Returning to A must not revive revision 1.
    with write_session(engine=engine) as session:
        select_target(
            case_id="case",
            selection=TargetSelection(target_speaker_id="A"),
            session=session,
            now=now,
        )
    process_case(case_id="case", engine=engine, now=now, models=[model])
    with read_session(engine=engine) as session:
        second = _assessments(session=session)[1:]
    assert len(second) == 1
    assert second[0].assessment_id != first[0].assessment_id
    assert second[0].target_revision == 3
    with write_session(engine=engine) as session:
        assert deliver_pending(case_id="case", session=session, now=now) == []
        create_intervention(case_id="case", since_us=0, session=session, now=now)
        delivered = deliver_pending(case_id="case", session=session, now=now)
        assert len(delivered) == 1
        assert delivered[0].assessment_ids == [second[0].assessment_id]
        assert deliver_pending(case_id="case", session=session, now=now) == []


def _assessments(*, session):
    return list(session.exec(select(Assessment).order_by(col(Assessment.assessment_id))).all())
