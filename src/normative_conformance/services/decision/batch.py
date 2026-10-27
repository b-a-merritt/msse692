from normative_conformance.schemas.observation import ObservationReplacement
from normative_conformance.services.observation.load_case_speech import IngestedObservation


def batch_end(
    *,
    ingested: list[IngestedObservation],
    revisions: list[ObservationReplacement],
    after_sequence: int,
    batch_size: int,
) -> int | None:
    """End a batch after up to `batch_size` new observations, without splitting a revised turn.

    Return None when nothing after `after_sequence` remains to be assessed.
    """
    new = sorted(row.sequence for row in ingested if row.sequence > after_sequence)
    if not new:
        return None
    end = new[:batch_size][-1]
    sequences = {row.observation.observation_id: row.sequence for row in ingested}
    for revision in revisions:
        turn = [sequences[identity] for identity in revision.replaced_observation_ids]
        if min(turn) <= end < max(turn):
            end = max(turn)
    return end
