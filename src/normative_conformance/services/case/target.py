from collections.abc import Iterable

from sqlalchemy import ScalarSelect
from sqlalchemy import SQLColumnExpression
from sqlalchemy import func
from sqlalchemy.orm import aliased
from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance.models.case import CaseLog
from normative_conformance.models.case import TargetAssignment


def resolve_speaker_order(*, labels: Iterable[str | None], order: int) -> str | None:
    """Resolve distinct labels in speech order, ignoring unresolved words."""
    if order not in (1, 2):
        raise ValueError("Target speaking order must be 1 or 2")
    seen: set[str] = set()
    for label in labels:
        if label is None or not label.strip() or label == "PENDING" or label in seen:
            continue
        seen.add(label)
        if len(seen) == order:
            return label
    return None


def current_revision(case_id: SQLColumnExpression[str]) -> ScalarSelect[int]:
    """Select the case's latest target revision, or NULL before any assignment."""
    latest = aliased(TargetAssignment)
    return (
        select(func.max(latest.target_revision)).where(latest.case_id == case_id).scalar_subquery()
    )


def current_assignment(*, case_id: str, session: Session) -> TargetAssignment | None:
    return session.exec(
        select(TargetAssignment)
        .where(TargetAssignment.case_id == case_id)
        .order_by(col(TargetAssignment.target_revision).desc())
        .limit(1)
    ).first()


def set_target_label(
    *, case_id: str, label: str | None, session: Session, assigned_at_us: int
) -> None:
    """Invalidate work from earlier mappings, including a change back to an old label."""
    current = current_assignment(case_id=case_id, session=session)
    if (current.speaker_id if current is not None else None) == label:
        return
    session.add(
        TargetAssignment(
            case_id=case_id,
            target_revision=current.target_revision + 1 if current is not None else 1,
            assigned_at_us=assigned_at_us,
            speaker_id=label,
        )
    )


def refresh_target(
    *, case: CaseLog, labels: Iterable[str | None], session: Session, assigned_at_us: int
) -> None:
    """Recompute order-based mappings without overriding an explicit selection."""
    if case.target_speaker_order is None:
        return
    set_target_label(
        case_id=case.case_id,
        label=resolve_speaker_order(labels=labels, order=case.target_speaker_order),
        session=session,
        assigned_at_us=assigned_at_us,
    )
