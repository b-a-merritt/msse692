from fastapi import APIRouter
from fastapi import Depends

from normative_conformance.routes import assessment
from normative_conformance.routes import capture
from normative_conformance.routes import case
from normative_conformance.routes import health
from normative_conformance.routes import intervention
from normative_conformance.routes import observation
from normative_conformance.routes.dependencies import reject_foreign_request

router = APIRouter(dependencies=[Depends(reject_foreign_request)])
router.include_router(health.router)
router.include_router(capture.router)
router.include_router(case.router)
router.include_router(observation.router)
router.include_router(assessment.router)
router.include_router(intervention.router)
