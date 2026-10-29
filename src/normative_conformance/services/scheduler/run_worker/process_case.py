import logging

from sqlalchemy import Engine
from typesafe_sdk import TypeSafeBadRequestError
from typesafe_sdk import TypeSafeClient
from typesafe_sdk import TypeSafeUnprocessableEntityError

from normative_conformance.clients import jev
from normative_conformance.database import read_session
from normative_conformance.database import write_session
from normative_conformance.schemas.decision import DecisionAnswers
from normative_conformance.schemas.decision import DecisionSnapshot
from normative_conformance.schemas.internal import Clock
from normative_conformance.services.assessment.store_assessment import store_assessment
from normative_conformance.services.case.get_case import get_case
from normative_conformance.services.case.progress import mark_handled
from normative_conformance.services.case.progress import read_handled_through
from normative_conformance.services.decision.batch import batch_end
from normative_conformance.services.decision.context import build_snapshot
from normative_conformance.services.intervention.create_intervention import create_intervention
from normative_conformance.services.observation.load_case_speech import load_case_speech
from normative_conformance.timestamps import to_microseconds

logger = logging.getLogger(__name__)


def process_case(
    *,
    case_id: str,
    max_batch_seconds: int,
    idle_seconds: int,
    context_seconds: int,
    engine: Engine,
    now: Clock,
    client: TypeSafeClient,
) -> int | None:
    """Assess the next closed batch, then commit its decisions and progress atomically.

    A batch the provider rejects would fail on every retry, so it is skipped. Other failures
    leave progress unchanged for the next poll to retry.
    """
    with read_session(engine=engine) as session:
        case = get_case(case_id=case_id, session=session)
        if case.target_speaker_id is None:
            return None
        after_sequence = read_handled_through(case_id=case_id, session=session)
        speech = load_case_speech(case_id=case_id, session=session)

    captured_at = now()
    through_sequence = batch_end(
        ingested=speech,
        target_speaker_id=case.target_speaker_id,
        after_sequence=after_sequence,
        max_seconds=max_batch_seconds,
        idle_seconds=idle_seconds,
        now=captured_at,
    )

    if through_sequence is None:
        return None

    snapshot = build_snapshot(
        case_id=case_id,
        target_speaker_id=case.target_speaker_id,
        target_revision=case.target_revision,
        ingested=speech,
        after_sequence=after_sequence,
        through_sequence=through_sequence,
        context_seconds=context_seconds,
        captured_at=captured_at,
    )
    # The provider runs outside both database transactions; the input is already fixed.
    try:
        answers, request_json = jev.evaluate(
            snapshot=snapshot,
            evidence=None,
            client=client,
        )
    except (TypeSafeBadRequestError, TypeSafeUnprocessableEntityError) as error:
        _skip_rejected(snapshot=snapshot, status=error.status, engine=engine)
        return None

    return _save(
        snapshot=snapshot,
        answers=answers,
        request_json=request_json,
        observation_keys={row.observation.observation_id: row.observation_key for row in speech},
        engine=engine,
        now=now,
    )


def _skip_rejected(*, snapshot: DecisionSnapshot, status: int, engine: Engine) -> None:
    logger.warning(
        "Batch rejected",
        extra={
            "event": "batch.rejected",
            "case_id": snapshot.case_id,
            "after_sequence": snapshot.after_sequence,
            "through_sequence": snapshot.through_sequence,
            "status": status,
        },
    )
    with write_session(engine=engine) as session:
        mark_handled(
            case_id=snapshot.case_id,
            target_revision=snapshot.target_revision,
            through_sequence=snapshot.through_sequence,
            session=session,
        )
        session.commit()


def _save(
    *,
    snapshot: DecisionSnapshot,
    answers: DecisionAnswers,
    request_json: str,
    observation_keys: dict[str, int],
    engine: Engine,
    now: Clock,
) -> int:
    with write_session(engine=engine) as session:
        completed_at_us = to_microseconds(value=now())
        assessment_id = store_assessment(
            session=session,
            snapshot=snapshot,
            answers=answers,
            request_json=request_json,
            observation_keys=observation_keys,
            completed_at_us=completed_at_us,
        )
        create_intervention(
            assessment_id=assessment_id,
            created_at_us=completed_at_us,
            answers=answers,
            session=session,
        )
        mark_handled(
            case_id=snapshot.case_id,
            target_revision=snapshot.target_revision,
            through_sequence=snapshot.through_sequence,
            session=session,
        )
        session.commit()
    return assessment_id
