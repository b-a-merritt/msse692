from sqlmodel import Session

from conversation_monitor.schemas.discovery import CaseTrace
from conversation_monitor.services.assessment.list_assessment_records import list_assessment_records
from conversation_monitor.services.case.list_cases import list_cases
from conversation_monitor.services.discovery.trace import trace


def load_traces(*, session: Session) -> list[CaseTrace]:
    """Build each case's trace for its current target, in case ID order."""
    return [
        trace(
            assessments=list_assessment_records(case_id=case.case_id, session=session),
            target_revision=case.target_revision,
        )
        for case in list_cases(session=session)
    ]
