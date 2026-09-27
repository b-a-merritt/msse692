from fastapi import APIRouter

from normative_conformance.routes import assessment
from normative_conformance.routes import health
from normative_conformance.routes import model
from normative_conformance.routes import observation

router = APIRouter()
router.include_router(health.router)
router.include_router(observation.router)
router.include_router(model.router)
router.include_router(assessment.router)
