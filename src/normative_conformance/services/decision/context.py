from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta

from normative_conformance.schemas.decision import DecisionSnapshot
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.schemas.observation import ObservationRecord
from normative_conformance.schemas.observation import ObservationReplacement


@dataclass(frozen=True, eq=False)
class _Speech:
    """Current speech and the ingested observations it represents."""

    row: ObservationInput
    sources: list[ObservationRecord]


def build_snapshot(
    *,
    case_id: str,
    target_speaker_id: str,
    target_revision: int,
    observations: list[ObservationRecord],
    revisions: list[ObservationReplacement],
    after_sequence: int,
    through_sequence: int,
    context_seconds: int,
    captured_at: datetime,
) -> DecisionSnapshot:
    """Describe the batch's speech as currently corrected, with recent speech as context.

    Speech is new when any observation it represents is after `after_sequence`. Revisions can
    remove all new speech, which leaves an empty snapshot with nothing to assess.
    """
    speech = _current_speech(
        observations=observations,
        revisions=revisions,
        through_sequence=through_sequence,
    )
    new = [item for item in speech if any(row.sequence > after_sequence for row in item.sources)]
    context = _recent(speech=speech, new=new, seconds=context_seconds)
    return DecisionSnapshot(
        case_id=case_id,
        target_speaker_id=target_speaker_id,
        target_revision=target_revision,
        after_sequence=after_sequence,
        through_sequence=through_sequence,
        captured_at=captured_at,
        observations=[item.row for item in context],
        new_observation_ids=[item.row.observation_id for item in context if item in new],
    )


def _current_speech(
    *,
    observations: list[ObservationRecord],
    revisions: list[ObservationReplacement],
    through_sequence: int,
) -> list[_Speech]:
    """Replace each revised turn with its latest correction, up to the end of the batch."""
    stored = {row.observation_id: row for row in observations if row.sequence <= through_sequence}
    # Revisions arrive in order, and each one replaces a whole turn.
    latest = {frozenset(revision.replaced_observation_ids): revision for revision in revisions}
    replaced = {identity for identities in latest for identity in identities}
    speech = [
        _Speech(row=_as_input(row), sources=[row])
        for identity, row in stored.items()
        if identity not in replaced
    ]
    for identities, revision in latest.items():
        turn = [stored[identity] for identity in identities if identity in stored]
        # A turn ingested after the batch is not part of it yet.
        if not turn:
            continue
        speech.extend(
            _Speech(row=row, sources=[source for source in turn if _overlaps(row, source)])
            for row in revision.observations
        )
    return speech


def _recent(*, speech: list[_Speech], new: list[_Speech], seconds: int) -> list[_Speech]:
    """Keep new speech and speech ending shortly before it, in time order."""
    if not new:
        return []
    cutoff = min(item.row.start_at for item in new) - timedelta(seconds=seconds)
    return sorted(
        (item for item in speech if item in new or item.row.end_at > cutoff),
        key=lambda item: (item.row.start_at, item.row.end_at, item.row.observation_id),
    )


def _overlaps(row: ObservationInput, source: ObservationRecord) -> bool:
    return row.start_at < source.end_at and source.start_at < row.end_at


def _as_input(row: ObservationRecord) -> ObservationInput:
    return ObservationInput.model_validate(
        row.model_dump(exclude={"received_at", "updated_at", "sequence"})
    )
