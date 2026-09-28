from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session
from sqlmodel import col

from normative_conformance import models
from normative_conformance.errors import StorageUnavailable
from normative_conformance.schemas.internal import Clock
from normative_conformance.schemas.intervention import Intervention
from normative_conformance.services.intervention.list_intervention_records import (
    list_intervention_records,
)
from normative_conformance.timestamps import to_microseconds


def deliver_pending(
    *,
    session: Session,
    now: Clock,
) -> list[Intervention]:
    """Mark pending interventions as sent and return them."""
    try:
        # Acquire the writer lock so each pending intervention is delivered once.
        session.connection()

        intervention_ids = list(
            session.exec(
                update(models.Intervention)
                .where(col(models.Intervention.sent_at_us).is_(None))
                .values(sent_at_us=to_microseconds(value=now()))
                .returning(col(models.Intervention.intervention_id))
            ).scalars()
        )
        if not intervention_ids:
            return []

        records = list_intervention_records(intervention_ids=intervention_ids, session=session)
        session.commit()

        return records
    except SQLAlchemyError as error:
        session.rollback()
        raise StorageUnavailable("The interventions could not be delivered") from error
