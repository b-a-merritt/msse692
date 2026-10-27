from sqlalchemy import ColumnElement
from sqlalchemy import and_
from sqlalchemy.orm import aliased
from sqlmodel import col
from sqlmodel import select

from normative_conformance.models.assessment import Assessment
from normative_conformance.models.intervention import Intervention
from normative_conformance.services.case.target import current_revision


def is_pending() -> ColumnElement[bool]:
    """Match undelivered interventions whose target mapping is still current."""
    source = aliased(Assessment)
    current = select(source.assessment_id).where(
        col(source.target_revision) == current_revision(col(source.case_id))
    )
    return and_(
        col(Intervention.sent_at_us).is_(None), col(Intervention.assessment_id).in_(current)
    )
