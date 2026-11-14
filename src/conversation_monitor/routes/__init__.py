from fastapi import APIRouter
from fastapi import Depends

from conversation_monitor.routes import assessment
from conversation_monitor.routes import capture
from conversation_monitor.routes import case
from conversation_monitor.routes import health
from conversation_monitor.routes import intervention
from conversation_monitor.routes import observation
from conversation_monitor.routes.dependencies import reject_foreign_request

router = APIRouter(dependencies=[Depends(reject_foreign_request)])
router.include_router(health.router)
router.include_router(capture.router)
router.include_router(case.router)
router.include_router(observation.router)
router.include_router(assessment.router)
router.include_router(intervention.router)
