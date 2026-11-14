from fastapi import APIRouter

from conversation_monitor.routes.dependencies import PathId
from conversation_monitor.routes.dependencies import ReadSession
from conversation_monitor.routes.dependencies import ServerClock
from conversation_monitor.routes.dependencies import WriteSession
from conversation_monitor.routes.errors import ERROR_RESPONSES
from conversation_monitor.schemas.common import ListResponse
from conversation_monitor.schemas.errors import ErrorEnvelope
from conversation_monitor.schemas.observation import ObservationInput
from conversation_monitor.schemas.observation import ObservationRecord
from conversation_monitor.services.observation.ingest import ingest
from conversation_monitor.services.observation.list_observations import list_observations

router = APIRouter(responses=ERROR_RESPONSES)


@router.post(
    "/api/v1/observations",
    status_code=201,
    operation_id="submitObservation",
    responses={409: {"model": ErrorEnvelope, "description": "Observation already exists"}},
)
def submit_observation(
    *,
    input: ObservationInput,
    session: WriteSession,
    now: ServerClock,
) -> ObservationRecord:
    """Store an observation."""
    return ingest(
        input=input,
        session=session,
        now=now,
    )


@router.get(
    "/api/v1/cases/{case_id}/observations",
    operation_id="listObservations",
)
def list_case_observations(
    *,
    case_id: PathId,
    session: ReadSession,
) -> ListResponse[ObservationRecord]:
    return ListResponse[ObservationRecord](
        items=list_observations(
            case_id=case_id,
            session=session,
        )
    )
