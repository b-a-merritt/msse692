import logging

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from normative_conformance.database import write_session
from normative_conformance.errors import CaptureFailure
from normative_conformance.errors import EnqueueFailed
from normative_conformance.models.case import CaseLog
from normative_conformance.schemas.internal import Clock
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.services.observation.ingest import stage_observation
from normative_conformance.services.scheduler.request_assessment import request_assessment
from normative_conformance.services.scheduler.state import SchedulerState

logger = logging.getLogger(__name__)


def store_observations(
    *,
    case_id: str,
    observations: list[ObservationInput],
    engine: Engine,
    now: Clock,
    scheduler: SchedulerState,
) -> None:
    if not observations:
        return
    try:
        with write_session(engine=engine) as session:
            session.connection()
            for observation in observations:
                stage_observation(input=observation, session=session, now=now)
            case = session.get(CaseLog, case_id)
            resolved = case is not None and case.target_speaker_id is not None
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
    if resolved:
        try:
            request_assessment(case_id=case_id, scheduler=scheduler)
        except EnqueueFailed as error:
            raise CaptureFailure("assessmentUnavailable") from error
