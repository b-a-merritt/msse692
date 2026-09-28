from typing import Annotated

from fastapi import APIRouter
from fastapi import Path

from normative_conformance.routes.dependencies import ReadSession
from normative_conformance.routes.errors import ERROR_RESPONSES
from normative_conformance.schemas.assessment import Assessment
from normative_conformance.schemas.common import ListResponse
from normative_conformance.services import assessment

router = APIRouter(responses=ERROR_RESPONSES)


@router.get(
    "/api/v1/cases/{case_id}/assessments",
    operation_id="listAssessments",
)
def list_assessments(
    *,
    case_id: Annotated[str, Path(strict=True, min_length=1, pattern=r"^[^/]+$")],
    session: ReadSession,
) -> ListResponse[Assessment]:
    """Return all stored case assessments in increasing ID order."""
    return ListResponse[Assessment](
        items=assessment.list_assessment_records(
            case_id=case_id,
            session=session,
        )
    )
