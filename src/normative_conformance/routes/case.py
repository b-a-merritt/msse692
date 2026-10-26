from typing import Annotated

from fastapi import APIRouter
from fastapi import Path

from normative_conformance.routes.dependencies import ReadSession
from normative_conformance.routes.dependencies import ServerClock
from normative_conformance.routes.dependencies import WriteSession
from normative_conformance.routes.errors import ERROR_RESPONSES
from normative_conformance.schemas.case import CaseRecord
from normative_conformance.schemas.case import TargetSelection
from normative_conformance.schemas.errors import ErrorEnvelope
from normative_conformance.services.case import selection

router = APIRouter(responses=ERROR_RESPONSES)
CaseId = Annotated[str, Path(strict=True, min_length=1, pattern=r"^[^/]+$")]


@router.put("/api/v1/cases/{case_id}/target", operation_id="selectTarget")
def select_target(
    *,
    case_id: CaseId,
    input: TargetSelection,
    session: WriteSession,
    now: ServerClock,
) -> CaseRecord:
    """Create or configure a case by speaking order or an explicit speaker label."""
    return selection.select_target(
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
def get_case(*, case_id: CaseId, session: ReadSession) -> CaseRecord:
    return selection.get_case(case_id=case_id, session=session)
