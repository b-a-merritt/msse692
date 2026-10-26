from fastapi import APIRouter

from normative_conformance.routes.dependencies import PathId
from normative_conformance.routes.dependencies import ReadSession
from normative_conformance.routes.errors import ERROR_RESPONSES
from normative_conformance.schemas.common import ListResponse
from normative_conformance.schemas.model import ModelVersion
from normative_conformance.services.model.get_model import get_model
from normative_conformance.services.model.list_models import list_models

router = APIRouter(responses=ERROR_RESPONSES)


@router.get(
    "/api/v1/models",
    operation_id="listModels",
)
def list_model_versions(
    *,
    session: ReadSession,
) -> ListResponse[ModelVersion]:
    """Return the complete immutable model catalog."""
    return ListResponse[ModelVersion](items=list_models(session=session))


@router.get(
    "/api/v1/models/{model_id}/versions/{version}",
    operation_id="getModel",
)
def get_model_version(
    *,
    model_id: PathId,
    version: PathId,
    session: ReadSession,
) -> ModelVersion:
    """Return one model version, including its rules and parameters."""
    return get_model(model_id=model_id, version=version, session=session)
