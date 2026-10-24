from collections.abc import Iterable

from normative_conformance.models.case import CaseLog


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
