from fastapi import APIRouter

from normative_conformance.routes import assessment
from normative_conformance.routes import capture
from normative_conformance.routes import case
from normative_conformance.routes import health
from normative_conformance.routes import intervention
from normative_conformance.routes import model
from normative_conformance.routes import observation

router = APIRouter()
router.include_router(health.router)
router.include_router(capture.router)
router.include_router(case.router)
router.include_router(observation.router)
router.include_router(model.router)
router.include_router(assessment.router)
router.include_router(intervention.router)
