import logging
from dataclasses import replace
from uuid import uuid4

from sqlalchemy import Engine

from normative_conformance.database import write_session
from normative_conformance.models.case import CaseLog
from normative_conformance.schemas.assessment import CaseSnapshot
from normative_conformance.schemas.internal import Clock
from normative_conformance.schemas.model import ModelVersion
from normative_conformance.services.assessment.check_repairs import check_repairs
from normative_conformance.services.assessment.evaluate_case import evaluate_case
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
        subject_speaker_id = case.target_speaker_id
        # These SQL evaluations share one locked snapshot and one server timestamp.
        detection = CaseSnapshot(
            case_id=case_id,
            evaluation_id=str(uuid4()),
            through_sequence=get_case_sequence(case_id=case_id, session=session),
            evaluated_at_us=to_microseconds(value=now()),
        )
        detections = evaluate_case(
            snapshot=detection,
            subject_speaker_id=subject_speaker_id,
            session=session,
            models=models,
        )
        repair_check = replace(detection, evaluation_id=str(uuid4()))
        repairs = check_repairs(
            snapshot=repair_check,
            subject_speaker_id=subject_speaker_id,
            session=session,
            models=models,
        )
        opened = should_open_intervention_window(
            assessments=detections, evaluation_id=detection.evaluation_id, resolutions_only=False
        ) or should_open_intervention_window(
            assessments=repairs, evaluation_id=repair_check.evaluation_id, resolutions_only=True
        )
        # find_repair selects the latest repair, so one re-evaluation covers every
        # reset in this snapshot. If that ordering changes, repeat detection and
        # repair checks until no further reset occurs.
        if any(
            row.status == "non-conformant"
            or (row.resolves_assessment_id is None and row.status == "conformant")
            for row in repairs
        ):
            redetection = replace(detection, evaluation_id=str(uuid4()))
            redetections = evaluate_case(
                snapshot=redetection,
                subject_speaker_id=subject_speaker_id,
                session=session,
                models=models,
            )
            opened |= should_open_intervention_window(
                assessments=redetections,
                evaluation_id=redetection.evaluation_id,
                resolutions_only=False,
            )
        case.last_handled_sequence = detection.through_sequence
        case.last_handled_target_revision = case.target_revision
        session.add(case)
        session.commit()
    logger.info(
        "Case processing committed",
        extra={
            "event": "case.processed",
            "case_id": case_id,
            "through_sequence": detection.through_sequence,
            "target_revision": case.target_revision,
        },
    )
    return detection.evaluated_at_us if opened else None
