from typing import Annotated

from fastapi import APIRouter
from fastapi import Query

from conversation_monitor.routes.dependencies import PathId
from conversation_monitor.routes.dependencies import QueryId
from conversation_monitor.routes.dependencies import ReadSession
from conversation_monitor.routes.dependencies import ServerClock
from conversation_monitor.routes.dependencies import WriteSession
from conversation_monitor.routes.errors import ERROR_RESPONSES
from conversation_monitor.schemas.common import ListResponse
from conversation_monitor.schemas.intervention import Intervention
from conversation_monitor.schemas.intervention import InterventionStatus
from conversation_monitor.services.intervention.deliver_pending import deliver_pending
from conversation_monitor.services.intervention.list_intervention_records import (
    list_intervention_records,
)

router = APIRouter(responses=ERROR_RESPONSES)


@router.get(
    "/api/v1/interventions",
    operation_id="listInterventions",
)
def list_interventions(
    *,
    case_id: QueryId | None = None,
    status: Annotated[InterventionStatus | None, Query()] = None,
    session: ReadSession,
    now: ServerClock,
) -> ListResponse[Intervention]:
    """Read all matching interventions without changing their delivery state."""
    return ListResponse[Intervention](
        items=list_intervention_records(
            case_id=case_id,
            status=status,
            session=session,
            now=now,
        )
    )


@router.post(
    "/api/v1/cases/{case_id}/interventions/deliver",
    operation_id="deliverInterventions",
)
def deliver_interventions(
    *,
    case_id: PathId,
    session: WriteSession,
    now: ServerClock,
) -> ListResponse[Intervention]:
    """Mark the case's pending interventions as sent and return them."""
    return ListResponse[Intervention](
        items=deliver_pending(
            case_id=case_id,
            session=session,
            now=now,
        ),
    )
