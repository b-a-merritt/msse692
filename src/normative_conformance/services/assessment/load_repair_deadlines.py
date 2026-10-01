from sqlalchemy import Engine

from normative_conformance.database import read_session
from normative_conformance.services.assessment.find_earliest_repair_deadlines import (
    find_earliest_repair_deadlines,
)
from normative_conformance.services.assessment.list_assessments import list_assessments


def load_repair_deadlines(*, engine: Engine) -> dict[str, int]:
    """Read earliest deadlines for unresolved pending assessments; let storage errors escape."""
    with read_session(engine=engine) as session:
        assessments = list_assessments(status="pending", unresolved=True, session=session)
        return find_earliest_repair_deadlines(assessments=assessments)
