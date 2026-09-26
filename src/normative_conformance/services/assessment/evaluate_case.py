from uuid import UUID

from sqlalchemy import Engine

from normative_conformance.schemas.assessment import Assessment
from normative_conformance.schemas.internal import Clock


def evaluate_case(
    *,
    case_id: str,
    evaluation_id: UUID,
    engine: Engine,
    now: Clock,
) -> list[Assessment]:
    """Capture case history, evaluate its models, and return the stored assessments."""
    raise NotImplementedError("Case evaluation is not implemented")
