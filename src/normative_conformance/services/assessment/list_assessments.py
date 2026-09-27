from sqlmodel import Session

from normative_conformance.schemas.assessment import Assessment
from normative_conformance.schemas.common import ListResponse


def list_assessments(
    *,
    case_id: str,
    session: Session,
) -> ListResponse[Assessment]:
    """Read all results in ID order; distinguish an empty case from an unknown case."""
    raise NotImplementedError("Assessment listing is not implemented")
