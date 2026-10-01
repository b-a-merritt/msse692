import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance import models
from normative_conformance.errors import StorageUnavailable
from normative_conformance.models.assessment import Assessment
from normative_conformance.schemas.internal import Clock
from normative_conformance.services.intervention.constants import INTERVENTION_MESSAGES
from normative_conformance.timestamps import to_microseconds

logger = logging.getLogger(__name__)


def create_intervention(
    *,
    case_id: str,
    since_us: int,
    session: Session,
    now: Clock,
) -> None:
    """Decide one intervention for the case's undesired matches confirmed since a time."""
    try:
        # Acquire the writer lock so no other decision can link the same assessments.
        session.connection()

        sources = _get_sources(case_id=case_id, since_us=since_us, session=session)
        if not sources:
            logger.info(
                "No eligible assessments for an intervention",
                extra={
                    "event": "intervention.no_sources",
                    "case_id": case_id,
                    "since_us": since_us,
                },
            )
            return

        intervention = models.Intervention(
            case_id=case_id,
            message=_select_message(model_ids={source.model_id for source in sources}),
            created_at_us=to_microseconds(value=now()),
        )

        session.add(intervention)
        session.flush()
        assert intervention.intervention_id is not None

        session.add_all(
            models.InterventionSource(
                intervention_id=intervention.intervention_id,
                assessment_id=source.assessment_id,
            )
            for source in sources
        )
        session.commit()
    except SQLAlchemyError as error:
        session.rollback()
        logger.exception(
            "Intervention rolled back",
            extra={"event": "intervention.rolled_back", "case_id": case_id, "since_us": since_us},
        )
        raise StorageUnavailable("The intervention could not be created") from error

    logger.info(
        "Intervention created",
        extra={
            "event": "intervention.created",
            "case_id": case_id,
            "intervention_id": intervention.intervention_id,
            "assessment_ids": [source.assessment_id for source in sources],
            "since_us": since_us,
            "intervention_message": intervention.message,
        },
    )


def _get_sources(
    *,
    case_id: str,
    since_us: int,
    session: Session,
) -> list[Assessment]:
    return list(
        session.exec(
            select(models.Assessment)
            .join(
                models.NormativeModelVersion,
                (col(models.NormativeModelVersion.model_id) == models.Assessment.model_id)
                & (col(models.NormativeModelVersion.version) == models.Assessment.model_version),
            )
            .where(
                models.Assessment.case_id == case_id,
                models.Assessment.status == "conformant",
                models.NormativeModelVersion.type == "undesired",
                col(models.Assessment.evaluated_at_us) >= since_us,
                col(models.Assessment.assessment_id).not_in(
                    select(models.InterventionSource.assessment_id)
                ),
            )
            .order_by(col(models.Assessment.assessment_id))
        ).all()
    )


def _select_message(*, model_ids: set[str]) -> str:
    for key, message in INTERVENTION_MESSAGES:
        if key <= model_ids:
            return message

    raise LookupError("No intervention message matches the assessments")
