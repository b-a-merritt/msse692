from typing import Annotated

from fastapi import APIRouter
from fastapi import Path

from normative_conformance.routes.dependencies import ReadSession
from normative_conformance.routes.errors import ERROR_RESPONSES
from normative_conformance.schemas.common import ListResponse
from normative_conformance.schemas.model import ModelVersion
from normative_conformance.services import model

router = APIRouter(responses=ERROR_RESPONSES)


@router.get(
    "/api/v1/models",
    operation_id="listModels",
)
def list_models(
    *,
    session: ReadSession,
) -> ListResponse[ModelVersion]:
    """Return the complete immutable model catalog."""
    return ListResponse[ModelVersion](items=model.list_models(session=session))


@router.get(
    "/api/v1/models/{model_id}/versions/{version}",
    operation_id="getModel",
)
def get_model(
    *,
    model_id: Annotated[str, Path(strict=True, min_length=1, pattern=r"^[^/]+$")],
    version: Annotated[str, Path(strict=True, min_length=1, pattern=r"^[^/]+$")],
    session: ReadSession,
) -> ModelVersion:
    """Return one model version, including its rules and parameters."""
    return model.get_model(model_id=model_id, version=version, session=session)
