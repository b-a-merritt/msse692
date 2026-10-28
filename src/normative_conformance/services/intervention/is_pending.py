from sqlalchemy import ColumnElement
from sqlalchemy import and_
from sqlalchemy import exists
from sqlalchemy.orm import aliased
from sqlmodel import col
from sqlmodel import select

from normative_conformance.models.assessment import Assessment
from normative_conformance.models.intervention import Intervention
from normative_conformance.services.case.target import current_revision

MAX_AGE_SECONDS = 60


def is_pending(*, now_us: int) -> ColumnElement[bool]:
    """Match undelivered interventions that still describe the current conversation.

    An intervention is stale once its target changes, once the target's later speech gets its
    own action, or after `MAX_AGE_SECONDS`.
    """
    source = aliased(Assessment)
    later = aliased(Assessment)
    superseded = exists().where(
        col(later.case_id) == col(source.case_id),
        col(later.target_revision) == col(source.target_revision),
        col(later.through_sequence) > col(source.through_sequence),
        col(later.action).is_not(None),
    )
    current = select(source.assessment_id).where(
        col(source.target_revision) == current_revision(col(source.case_id)), ~superseded
    )
    return and_(
        col(Intervention.sent_at_us).is_(None),
        col(Intervention.created_at_us) > now_us - MAX_AGE_SECONDS * 1_000_000,
        col(Intervention.assessment_id).in_(current),
    )
