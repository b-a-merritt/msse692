from typing import Annotated
from typing import Literal

from fastapi import APIRouter
from fastapi import Path
from fastapi import Query

from normative_conformance.routes.dependencies import ReadSession
from normative_conformance.routes.dependencies import ServerClock
from normative_conformance.routes.dependencies import WriteSession
from normative_conformance.routes.errors import ERROR_RESPONSES
from normative_conformance.schemas.common import ListResponse
from normative_conformance.schemas.intervention import Intervention
from normative_conformance.services import intervention

router = APIRouter(responses=ERROR_RESPONSES)


@router.get(
    "/api/v1/interventions",
    operation_id="listInterventions",
)
def list_interventions(
    *,
    case_id: Annotated[str | None, Query(strict=True, min_length=1, pattern=r"^[^/]+$")] = None,
    status: Annotated[Literal["pending", "sent"] | None, Query()] = None,
    session: ReadSession,
) -> ListResponse[Intervention]:
    """Read all matching interventions without changing their delivery state."""
    return ListResponse[Intervention](
        items=intervention.list_intervention_records(
            case_id=case_id,
            status=status,
            session=session,
        )
    )


@router.post(
    "/api/v1/cases/{case_id}/interventions/deliver",
    operation_id="deliverInterventions",
)
def deliver_interventions(
    *,
    case_id: Annotated[str, Path(strict=True, min_length=1, pattern=r"^[^/]+$")],
    session: WriteSession,
    now: ServerClock,
) -> ListResponse[Intervention]:
    """Mark the case's pending interventions as sent and return them."""
    return ListResponse[Intervention](
        items=intervention.deliver_pending(
            case_id=case_id,
            session=session,
            now=now,
        ),
    )
