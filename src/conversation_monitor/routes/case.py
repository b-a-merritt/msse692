from fastapi import APIRouter

from conversation_monitor.routes.dependencies import PathId
from conversation_monitor.routes.dependencies import ReadSession
from conversation_monitor.routes.dependencies import ServerClock
from conversation_monitor.routes.dependencies import WriteSession
from conversation_monitor.routes.errors import ERROR_RESPONSES
from conversation_monitor.schemas.case import CaseRecord
from conversation_monitor.schemas.case import TargetSelection
from conversation_monitor.schemas.errors import ErrorEnvelope
from conversation_monitor.services.case.get_case import get_case as load_case
from conversation_monitor.services.case.select_target import select_target as store_target

router = APIRouter(responses=ERROR_RESPONSES)


@router.put("/api/v1/cases/{case_id}/target", operation_id="selectTarget")
def select_target(
    *,
    case_id: PathId,
    input: TargetSelection,
    session: WriteSession,
    now: ServerClock,
) -> CaseRecord:
    """Create or configure a case by speaking order or an explicit speaker label."""
    return store_target(
        case_id=case_id,
        selection=input,
        session=session,
        now=now,
    )


@router.get(
    "/api/v1/cases/{case_id}",
    operation_id="getCase",
    responses={404: {"model": ErrorEnvelope, "description": "Case not found"}},
)
def get_case(*, case_id: PathId, session: ReadSession) -> CaseRecord:
    return load_case(case_id=case_id, session=session)
