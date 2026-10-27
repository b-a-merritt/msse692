from normative_conformance.schemas.observation import ObservationRecord
from normative_conformance.schemas.observation import ObservationReplacement


def batch_end(
    *,
    observations: list[ObservationRecord],
    revisions: list[ObservationReplacement],
    after_sequence: int,
    batch_size: int,
) -> int | None:
    """End a batch after up to `batch_size` new observations, without splitting a revised turn.

    Return None when nothing after `after_sequence` remains to be assessed.
    """
    new = sorted(row.sequence for row in observations if row.sequence > after_sequence)
    if not new:
        return None
    end = new[:batch_size][-1]
    sequences = {row.observation_id: row.sequence for row in observations}
    for revision in revisions:
        turn = [sequences[identity] for identity in revision.replaced_observation_ids]
        if min(turn) <= end < max(turn):
            end = max(turn)
    return end
