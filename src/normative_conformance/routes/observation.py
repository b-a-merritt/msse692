from typing import Annotated

from fastapi import APIRouter
from fastapi import Path

from normative_conformance.routes.dependencies import ReadSession
from normative_conformance.routes.dependencies import Scheduler
from normative_conformance.routes.dependencies import ServerClock
from normative_conformance.routes.dependencies import WriteSession
from normative_conformance.routes.errors import ERROR_RESPONSES
from normative_conformance.schemas.common import ListResponse
from normative_conformance.schemas.errors import ErrorEnvelope
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.schemas.observation import ObservationRecord
from normative_conformance.services import observation

router = APIRouter(responses=ERROR_RESPONSES)


@router.post(
    "/api/v1/observations",
    status_code=202,
    operation_id="submitObservation",
    responses={409: {"model": ErrorEnvelope, "description": "Observation already exists"}},
)
def submit_observation(
    *,
    input: ObservationInput,
    session: WriteSession,
    now: ServerClock,
    scheduler: Scheduler,
) -> ObservationRecord:
    """Commit an observation, then request assessment of its case."""
    return observation.ingest(
        input=input,
        session=session,
        now=now,
        scheduler=scheduler,
    )


@router.get(
    "/api/v1/cases/{case_id}/observations",
    operation_id="listObservations",
)
def list_observations(
    *,
    case_id: Annotated[str, Path(strict=True, min_length=1, pattern=r"^[^/]+$")],
    session: ReadSession,
) -> ListResponse[ObservationRecord]:
    return observation.list_observations(
        case_id=case_id,
        session=session,
    )
