import logging

from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from conversation_monitor import models
from conversation_monitor.errors import StorageUnavailable
from conversation_monitor.schemas.internal import Clock
from conversation_monitor.schemas.intervention import Intervention
from conversation_monitor.services.intervention.is_pending import is_pending
from conversation_monitor.services.intervention.list_intervention_records import (
    list_intervention_records,
)
from conversation_monitor.timestamps import to_microseconds

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
                    col(models.Intervention.assessment_id).in_(
                        select(models.Assessment.assessment_id).where(
                            models.Assessment.case_id == case_id
                        )
                    ),
                    is_pending(now_us=sent_at_us),
                )
                .values(sent_at_us=sent_at_us)
                .returning(col(models.Intervention.intervention_id))
            ).scalars()
        )
        if not intervention_ids:
            return []

        records = list_intervention_records(
            intervention_ids=intervention_ids, session=session, now=now
        )
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
