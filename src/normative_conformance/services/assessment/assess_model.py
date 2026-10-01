import logging

from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance.models.assessment import Assessment
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.assessment import CaseSnapshot
from normative_conformance.schemas.model import ModelVersion
from normative_conformance.services.assessment.create_assessment import create_assessment
from normative_conformance.services.model.evaluate_model import evaluate_model

logger = logging.getLogger(__name__)


def assess_model(
    *,
    model: ModelVersion,
    snapshot: CaseSnapshot,
    subject_speaker_id: str,
    last_repair: Observation | None,
    session: Session,
) -> Assessment | None:
    """Reuse an active occurrence or append a newly detected match."""
    previous = _get_previous_assessment(model=model, case_id=snapshot.case_id, session=session)
    if previous is not None and previous.status == "pending":
        _log_decision(
            message="Pending match reused",
            event="model.pending_reused",
            model=model,
            snapshot=snapshot,
            assessment=previous,
        )
        return previous

    if not evaluate_model(
        model=model,
        case_id=snapshot.case_id,
        subject_speaker_id=subject_speaker_id,
        through_sequence=snapshot.through_sequence,
        session=session,
        after_observation=last_repair,
    ):
        _log_decision(
            message="Model did not match",
            event="model.no_match",
            model=model,
            snapshot=snapshot,
            assessment=None,
        )
        return None

    if previous is not None and previous.status == "conformant":
        if previous.resolves_assessment_id is not None:
            original = session.get(Assessment, previous.resolves_assessment_id)
            assert original is not None
        else:
            original = previous
        # A resolution can include later speech; reuse depends on the original evidence.
        if evaluate_model(
            model=model,
            case_id=snapshot.case_id,
            subject_speaker_id=subject_speaker_id,
            through_sequence=original.through_sequence,
            session=session,
            after_observation=last_repair,
        ):
            _log_decision(
                message="Confirmed match reused",
                event="model.match_reused",
                model=model,
                snapshot=snapshot,
                assessment=previous,
            )
            return previous

    deadline = (
        snapshot.evaluated_at_us + model.repair_allowance_us
        if model.repair_allowance_us is not None
        else None
    )

    created = create_assessment(
        model=model,
        snapshot=snapshot,
        status="pending" if deadline is not None else "conformant",
        session=session,
        next_due_at_us=deadline,
    )
    _log_decision(
        message="Model matched",
        event="model.matched",
        model=model,
        snapshot=snapshot,
        assessment=created,
    )
    return created


def _log_decision(
    *,
    message: str,
    event: str,
    model: ModelVersion,
    snapshot: CaseSnapshot,
    assessment: Assessment | None,
) -> None:
    logger.info(
        message,
        extra={
            "event": event,
            "case_id": snapshot.case_id,
            "evaluation_id": snapshot.evaluation_id,
            "model_id": model.model_id,
            "version": model.version,
            "through_sequence": snapshot.through_sequence,
            "assessment_id": assessment.assessment_id if assessment else None,
            "status": assessment.status if assessment else None,
            "next_due_at_us": assessment.next_due_at_us if assessment else None,
        },
    )


def _get_previous_assessment(
    *, model: ModelVersion, case_id: str, session: Session
) -> Assessment | None:
    """Prefer the newest unresolved pending match, otherwise the latest result."""
    query = (
        select(Assessment)
        .where(
            Assessment.case_id == case_id,
            Assessment.model_id == model.model_id,
            Assessment.model_version == model.version,
        )
        .order_by(col(Assessment.assessment_id).desc())
        .limit(1)
    )
    resolved = select(Assessment.resolves_assessment_id).where(
        col(Assessment.resolves_assessment_id).is_not(None)
    )
    pending = session.exec(
        query.where(Assessment.status == "pending", col(Assessment.assessment_id).not_in(resolved))
    ).first()
    if pending is not None:
        return pending
    return session.exec(query).first()
