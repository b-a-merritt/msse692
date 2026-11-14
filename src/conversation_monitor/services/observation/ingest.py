import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from conversation_monitor.errors import ObservationExists
from conversation_monitor.errors import StorageUnavailable
from conversation_monitor.schemas.internal import Clock
from conversation_monitor.schemas.observation import ObservationInput
from conversation_monitor.schemas.observation import ObservationRecord
from conversation_monitor.services.observation.stage_observation import stage_observation

logger = logging.getLogger(__name__)


def ingest(
    *,
    input: ObservationInput,
    session: Session,
    now: Clock,
) -> ObservationRecord:
    """Commit an observation for database polling."""
    try:
        record = stage_observation(input=input, session=session, now=now)
        session.commit()
    except SQLAlchemyError as error:
        session.rollback()
        logger.exception(
            "Observation rolled back",
            extra={
                "event": "observation.rolled_back",
                "case_id": input.case_id,
                "observation_id": input.observation_id,
            },
        )
        raise StorageUnavailable("The observation could not be stored") from error
    except ObservationExists:
        session.rollback()
        raise

    logger.info(
        "Observation committed",
        extra={
            "event": "observation.committed",
            "case_id": record.case_id,
            "observation_id": record.observation_id,
            "sequence": record.sequence,
        },
    )

    return record
