from sqlmodel import Session

from normative_conformance.schemas.assessment import AssessmentList


def list_assessments(
    *,
    case_id: str,
    session: Session,
) -> AssessmentList:
    """Read all results in ID order; distinguish an empty case from an unknown case."""
    raise NotImplementedError("Assessment listing is not implemented")
