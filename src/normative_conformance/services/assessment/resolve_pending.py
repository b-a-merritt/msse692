import logging
from typing import Literal

from sqlmodel import Session

from normative_conformance.models.assessment import Assessment
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.assessment import CaseSnapshot
from normative_conformance.schemas.model import ModelVersion
from normative_conformance.services.assessment.create_assessment import create_assessment
from normative_conformance.services.model.evaluate_model import evaluate_model
from normative_conformance.services.model.find_repair import find_repair

logger = logging.getLogger(__name__)


def resolve_pending(
    *,
    pending: Assessment,
    model: ModelVersion,
    repair_models: list[ModelVersion],
    snapshot: CaseSnapshot,
    subject_speaker_id: str,
    session: Session,
) -> Assessment:
    """Keep the original deadline, or append a resolution when repaired or overdue."""
    assert pending.next_due_at_us is not None
    repair = find_repair(
        models=repair_models,
        case_id=pending.case_id,
        subject_speaker_id=subject_speaker_id,
        through_sequence=snapshot.through_sequence,
        session=session,
        deadline_at_us=pending.next_due_at_us,
    )
    repaired_by: Observation | None = None
    if repair is not None:
        _, observation = repair
        # A timely repair must remove the original match at its speech boundary.
        if not evaluate_model(
            model=model,
            case_id=pending.case_id,
            subject_speaker_id=subject_speaker_id,
            through_sequence=pending.through_sequence,
            session=session,
            after_observation=observation,
        ):
            repaired_by = observation

    if repaired_by is not None:
        status: Literal["conformant", "non-conformant"] = "non-conformant"
        observation_ids = [repaired_by.observation_id]
    elif snapshot.evaluated_at_us < pending.next_due_at_us:
        _log_resolution(
            message="Pending match still awaiting repair",
            event="pending.waiting",
            pending=pending,
            snapshot=snapshot,
            resolution=None,
            repair_observation_id=None,
        )
        return pending
    else:
        status = "conformant"
        observation_ids = []

    resolution = create_assessment(
        model=model,
        snapshot=snapshot,
        status=status,
        session=session,
        resolves_assessment_id=pending.assessment_id,
        observation_ids=observation_ids,
    )
    if repaired_by is not None:
        _log_resolution(
            message="Pending match repaired",
            event="pending.repaired",
            pending=pending,
            snapshot=snapshot,
            resolution=resolution,
            repair_observation_id=repaired_by.observation_id,
        )
    else:
        _log_resolution(
            message="Pending match confirmed after its repair deadline",
            event="pending.expired",
            pending=pending,
            snapshot=snapshot,
            resolution=resolution,
            repair_observation_id=None,
        )
    return resolution


def _log_resolution(
    *,
    message: str,
    event: str,
    pending: Assessment,
    snapshot: CaseSnapshot,
    resolution: Assessment | None,
    repair_observation_id: str | None,
) -> None:
    logger.info(
        message,
        extra={
            "event": event,
            "case_id": pending.case_id,
            "evaluation_id": snapshot.evaluation_id,
            "pending_assessment_id": pending.assessment_id,
            "model_id": pending.model_id,
            "version": pending.model_version,
            "next_due_at_us": pending.next_due_at_us,
            "through_sequence": snapshot.through_sequence,
            "repair_observation_id": repair_observation_id,
            "assessment_id": resolution.assessment_id if resolution else None,
        },
    )
