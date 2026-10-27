from sqlalchemy import Engine
from typesafe_sdk import TypeSafeClient

from normative_conformance.clients import jev
from normative_conformance.database import read_session
from normative_conformance.database import write_session
from normative_conformance.models.assessment import Assessment
from normative_conformance.schemas.internal import Clock
from normative_conformance.services.assessment.store_assessment import store_assessment
from normative_conformance.services.case.target import current_assignment
from normative_conformance.services.decision.batch import batch_end
from normative_conformance.services.decision.context import build_snapshot
from normative_conformance.services.observation.load_case_speech import load_case_speech
from normative_conformance.services.scheduler.run_worker.progress import mark_handled
from normative_conformance.services.scheduler.run_worker.progress import read_handled_through
from normative_conformance.timestamps import to_microseconds


def process_case(
    *,
    case_id: str,
    batch_size: int,
    context_seconds: int,
    engine: Engine,
    now: Clock,
    client: TypeSafeClient,
) -> Assessment | None:
    """Assess a fixed batch, then commit its decisions and progress atomically.

    A batch whose new speech was entirely removed by revisions is marked handled unassessed.
    """
    with read_session(engine=engine) as session:
        assignment = current_assignment(case_id=case_id, session=session)
        if assignment is None or assignment.speaker_id is None:
            return None
        after_sequence = read_handled_through(case_id=case_id, session=session)
        speech = load_case_speech(case_id=case_id, session=session)
        through_sequence = batch_end(
            ingested=speech.ingested,
            revisions=speech.revisions,
            after_sequence=after_sequence,
            batch_size=batch_size,
        )
        if through_sequence is None:
            return None
        snapshot = build_snapshot(
            case_id=case_id,
            target_speaker_id=assignment.speaker_id,
            target_revision=assignment.target_revision,
            ingested=speech.ingested,
            revisions=speech.revisions,
            after_sequence=after_sequence,
            through_sequence=through_sequence,
            context_seconds=context_seconds,
            captured_at=now(),
        )
    if not snapshot.new_observation_ids:
        with write_session(engine=engine) as session:
            mark_handled(snapshot=snapshot, session=session)
            session.commit()
        return None
    # The provider runs outside both database transactions; the input is already fixed.
    answers, request_json = jev.evaluate(snapshot=snapshot, client=client)
    with write_session(engine=engine) as session:
        assessment = store_assessment(
            session=session,
            snapshot=snapshot,
            answers=answers,
            request_json=request_json,
            observation_keys=speech.observation_keys,
            completed_at_us=to_microseconds(value=now()),
        )
        mark_handled(snapshot=snapshot, session=session)
        session.commit()
    return assessment
