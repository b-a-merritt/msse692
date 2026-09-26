from fastapi import APIRouter

from normative_conformance.routes import observation

router = APIRouter()
router.include_router(observation.router)
