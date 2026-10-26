from fastapi import APIRouter

from normative_conformance.routes.dependencies import PathId
from normative_conformance.routes.dependencies import ReadSession
from normative_conformance.routes.dependencies import ServerClock
from normative_conformance.routes.dependencies import WriteSession
from normative_conformance.routes.errors import ERROR_RESPONSES
from normative_conformance.schemas.common import ListResponse
from normative_conformance.schemas.errors import ErrorEnvelope
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.schemas.observation import ObservationRecord
from normative_conformance.services.observation.ingest import ingest
from normative_conformance.services.observation.list_observations import list_observations

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
