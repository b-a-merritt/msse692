from sqlmodel import Session

from normative_conformance.schemas.discovery import CaseTrace
from normative_conformance.services.assessment.list_assessment_records import (
    list_assessment_records,
)
from normative_conformance.services.case.list_cases import list_cases
from normative_conformance.services.discovery.trace import trace


def load_traces(*, session: Session) -> list[CaseTrace]:
    """Build each case's trace for its current target, in case ID order."""
    traces = []

    for case in list_cases(session=session):
        assessments = [
            assessment
            for assessment in list_assessment_records(case_id=case.case_id, session=session)
            if assessment.target_revision == case.target_revision
        ]
        traces.append(
            CaseTrace(
                events=trace(
                    assessments=assessments,
                    target_revision=case.target_revision,
                ),
                assessment_ids=[assessment.assessment_id for assessment in assessments],
            )
        )
    return traces
