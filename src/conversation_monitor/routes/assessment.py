from fastapi import APIRouter

from conversation_monitor.routes.dependencies import PathId
from conversation_monitor.routes.dependencies import ReadSession
from conversation_monitor.routes.errors import ERROR_RESPONSES
from conversation_monitor.schemas.assessment import Assessment
from conversation_monitor.schemas.common import ListResponse
from conversation_monitor.services.assessment.list_assessment_records import list_assessment_records

router = APIRouter(responses=ERROR_RESPONSES)


@router.get(
    "/api/v1/cases/{case_id}/assessments",
    operation_id="listAssessments",
)
def list_assessments(
    *,
    case_id: PathId,
    session: ReadSession,
) -> ListResponse[Assessment]:
    """Return all stored case assessments in increasing ID order."""
    return ListResponse[Assessment](
        items=list_assessment_records(
            case_id=case_id,
            session=session,
        )
    )
