import logging

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from normative_conformance.database import write_session
from normative_conformance.errors import CaptureFailure
from normative_conformance.schemas.internal import Clock
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.services.observation.stage_observation import stage_observation

logger = logging.getLogger(__name__)


def store_observations(
    *,
    case_id: str,
    observations: list[ObservationInput],
    engine: Engine,
    now: Clock,
) -> None:
    if not observations:
        return
    try:
        with write_session(engine=engine) as session:
            session.connection()
            for observation in observations:
                stage_observation(input=observation, session=session, now=now)
            session.commit()
    except SQLAlchemyError as error:
        raise CaptureFailure("storageUnavailable") from error
    logger.info(
        "Finalized speech stored",
        extra={
            "event": "capture.observations_stored",
            "case_id": case_id,
            "count": len(observations),
        },
    )
