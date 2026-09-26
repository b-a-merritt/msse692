from sqlmodel import Session

from normative_conformance.schemas.assessment import Assessment


def get_assessment(
    *,
    assessment_id: int,
    session: Session,
) -> Assessment:
    """Read a result with its exact extent and explanation; unknown IDs raise NotFound."""
    raise NotImplementedError("Assessment lookup is not implemented")
