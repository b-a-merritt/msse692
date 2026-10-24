import logging

from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance import models
from normative_conformance.errors import StorageUnavailable
from normative_conformance.models.case import CaseLog
from normative_conformance.schemas.internal import Clock
from normative_conformance.schemas.intervention import Intervention
from normative_conformance.services.intervention.list_intervention_records import (
    list_intervention_records,
)
from normative_conformance.timestamps import to_microseconds

logger = logging.getLogger(__name__)


def deliver_pending(
    *,
    case_id: str,
    session: Session,
    now: Clock,
) -> list[Intervention]:
    """Mark the case's pending interventions as sent and return them."""
    try:
        # Acquire the writer lock so each pending intervention is delivered once.
        session.connection()

        sent_at_us = to_microseconds(value=now())
        intervention_ids = list(
            session.exec(
                update(models.Intervention)
                .where(
                    col(models.Intervention.case_id) == case_id,
                    col(models.Intervention.sent_at_us).is_(None),
                    select(CaseLog.case_id)
                    .where(
                        CaseLog.case_id == models.Intervention.case_id,
                        CaseLog.target_revision == models.Intervention.target_revision,
                        CaseLog.target_speaker_id == models.Intervention.subject_speaker_id,
                    )
                    .exists(),
                )
                .values(sent_at_us=sent_at_us)
                .returning(col(models.Intervention.intervention_id))
            ).scalars()
        )
        if not intervention_ids:
            return []

        records = list_intervention_records(intervention_ids=intervention_ids, session=session)
        session.commit()
        logger.info(
            "Interventions delivered",
            extra={
                "event": "intervention.delivered",
                "case_id": case_id,
                "intervention_ids": intervention_ids,
                "sent_at_us": sent_at_us,
            },
        )
        return records
    except SQLAlchemyError as error:
        session.rollback()
        logger.exception(
            "Intervention delivery rolled back",
            extra={"event": "intervention.delivery_rolled_back"},
        )
        raise StorageUnavailable("The interventions could not be delivered") from error
