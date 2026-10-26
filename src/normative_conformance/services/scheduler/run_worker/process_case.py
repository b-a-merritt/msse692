import logging
from typing import Literal
from typing import cast
from uuid import uuid4

from sqlalchemy import Engine

from normative_conformance.database import write_session
from normative_conformance.models.case import CaseLog
from normative_conformance.schemas.internal import Clock
from normative_conformance.schemas.model import ModelVersion
from normative_conformance.services.assessment import check_repairs
from normative_conformance.services.assessment import evaluate_case
from normative_conformance.services.intervention.should_open_intervention_window import (
    should_open_intervention_window,
)
from normative_conformance.services.observation.get_case_sequence import get_case_sequence
from normative_conformance.timestamps import to_microseconds

logger = logging.getLogger(__name__)


def process_case(
    *, case_id: str, engine: Engine, now: Clock, models: list[ModelVersion]
) -> int | None:
    """Commit detection, repairs and progress together; return a new window's start."""
    with write_session(engine=engine) as session:
        session.connection()
        case = session.get(CaseLog, case_id)
        if case is None or case.target_speaker_id is None:
            return None
        started_at = now()
        started_at_us = to_microseconds(value=started_at)
        through_sequence = get_case_sequence(case_id=case_id, session=session)
        opened = False
        # These SQL evaluations share one locked snapshot and one server timestamp.
        for kind, evaluate in [("assess_case", evaluate_case), ("check_repairs", check_repairs)]:
            evaluation_id = uuid4()
            results = evaluate(
                case_id=case_id,
                evaluation_id=evaluation_id,
                session=session,
                now=lambda: started_at,
                models=models,
            )
            opened |= should_open_intervention_window(
                assessments=results,
                task_kind=cast(Literal["assess_case", "check_repairs"], kind),
                evaluation_id=str(evaluation_id),
            )
        # find_repair selects the latest repair, so one re-evaluation covers every
        # reset in this snapshot. If that ordering changes, repeat detection and
        # repair checks until no further reset occurs.
        if any(
            row.status == "non-conformant"
            or (row.resolves_assessment_id is None and row.status == "conformant")
            for row in results
        ):
            evaluation_id = uuid4()
            results = evaluate_case(
                case_id=case_id,
                evaluation_id=evaluation_id,
                session=session,
                now=lambda: started_at,
                models=models,
            )
            opened |= should_open_intervention_window(
                assessments=results,
                task_kind="assess_case",
                evaluation_id=str(evaluation_id),
            )
        case.last_handled_sequence = through_sequence
        case.last_handled_target_revision = case.target_revision
        session.add(case)
        session.commit()
    logger.info(
        "Case processing committed",
        extra={
            "event": "case.processed",
            "case_id": case_id,
            "through_sequence": through_sequence,
            "target_revision": case.target_revision,
        },
    )
    return started_at_us if opened else None
