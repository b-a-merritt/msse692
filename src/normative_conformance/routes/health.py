from fastapi import APIRouter

from normative_conformance.routes.dependencies import AssessmentWorker
from normative_conformance.routes.dependencies import ReadSession
from normative_conformance.routes.dependencies import Scheduler
from normative_conformance.routes.errors import ERROR_RESPONSES
from normative_conformance.schemas.health import Liveness
from normative_conformance.schemas.health import Readiness
from normative_conformance.services import health

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
def readiness(
    *,
    session: ReadSession,
    scheduler: Scheduler,
    worker: AssessmentWorker,
) -> Readiness:
    """Report database, queue, and assessment-worker availability."""
    return health.readiness(session=session, scheduler=scheduler, worker=worker)
