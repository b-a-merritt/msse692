from typing import Annotated

from fastapi import APIRouter
from fastapi import Path

from normative_conformance.routes.dependencies import ReadSession
from normative_conformance.routes.errors import ERROR_RESPONSES
from normative_conformance.schemas.assessment import Assessment
from normative_conformance.schemas.assessment import Explanation
from normative_conformance.schemas.assessment import Extent
from normative_conformance.schemas.common import ListResponse
from normative_conformance.services import assessment
from normative_conformance.services.model.get_subject_speaker_id import get_subject_speaker_id
from normative_conformance.services.observation.get_case_history import get_case_history
from normative_conformance.timestamps import from_microseconds

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
    rows = assessment.list_assessments(case_id=case_id, session=session)
    if not rows:
        return ListResponse[Assessment](items=[])

    subject_speaker_id = get_subject_speaker_id(session=session)
    history = get_case_history(
        case_id=case_id,
        through_sequence=max(row.through_sequence for row in rows),
        session=session,
    )
    records = []
    for row in rows:
        observation_ids = [
            observation.observation_id
            for observation in history
            if observation.sequence <= row.through_sequence
        ]
        records.append(
            Assessment.model_validate(
                {
                    "assessment_id": row.assessment_id,
                    "resolves_assessment_id": row.resolves_assessment_id,
                    "evaluation_id": row.evaluation_id,
                    "case_id": row.case_id,
                    "subject_speaker_id": subject_speaker_id,
                    "model_id": row.model_id,
                    "model_version": row.model_version,
                    "evaluated_at": from_microseconds(value=row.evaluated_at_us),
                    "status": row.status,
                    "extent": Extent(
                        through_sequence=row.through_sequence,
                        observation_count=len(observation_ids),
                        observation_ids=observation_ids,
                    ),
                    "explanation": Explanation.model_validate_json(row.explanation_json),
                    "next_due_at": (
                        from_microseconds(value=row.next_due_at_us)
                        if row.next_due_at_us is not None
                        else None
                    ),
                }
            )
        )

    return ListResponse[Assessment](items=records)
