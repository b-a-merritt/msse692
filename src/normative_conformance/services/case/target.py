from collections.abc import Iterable

from sqlalchemy import Exists
from sqlmodel import select

from normative_conformance.models.assessment import Assessment
from normative_conformance.models.case import CaseLog
from normative_conformance.models.intervention import Intervention


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


def set_target_label(*, case: CaseLog, label: str | None) -> None:
    """Invalidate work from earlier mappings, including a change back to an old label."""
    if case.target_speaker_id != label:
        case.target_speaker_id = label
        case.target_revision += 1


def refresh_target(*, case: CaseLog, labels: Iterable[str | None]) -> None:
    """Recompute order-based mappings without overriding an explicit selection."""
    if case.target_speaker_manual or case.target_speaker_order is None:
        return
    set_target_label(
        case=case,
        label=resolve_speaker_order(labels=labels, order=case.target_speaker_order),
    )


def for_current_target(record: type[Assessment] | type[Intervention]) -> Exists:
    return (
        select(CaseLog.case_id)
        .where(
            CaseLog.case_id == record.case_id,
            CaseLog.target_revision == record.target_revision,
            CaseLog.target_speaker_id == record.subject_speaker_id,
        )
        .exists()
    )
