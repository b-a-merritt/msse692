from fastapi import APIRouter

from conversation_monitor.routes.dependencies import AssessmentWorker
from conversation_monitor.routes.dependencies import ReadSession
from conversation_monitor.routes.dependencies import WorkerStopped
from conversation_monitor.routes.errors import ERROR_RESPONSES
from conversation_monitor.schemas.health import Liveness
from conversation_monitor.schemas.health import Readiness
from conversation_monitor.services.health.readiness import readiness

router = APIRouter(
    prefix="/health",
    responses=ERROR_RESPONSES,
)


@router.get(
    "/live",
    operation_id="liveness",
)
def liveness() -> Liveness:
    """Report HTTP process responsiveness."""
    return Liveness(status="live")


@router.get(
    "/ready",
    operation_id="readiness",
)
def check_readiness(
    *,
    session: ReadSession,
    stopped: WorkerStopped,
    worker: AssessmentWorker,
) -> Readiness:
    """Report database and assessment-worker availability."""
    return readiness(session=session, stopped=stopped, worker=worker)
