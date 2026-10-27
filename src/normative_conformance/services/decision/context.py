from datetime import datetime
from datetime import timedelta

from normative_conformance.schemas.decision import DecisionSnapshot
from normative_conformance.services.observation.load_case_speech import IngestedObservation


def build_snapshot(
    *,
    case_id: str,
    target_speaker_id: str,
    target_revision: int,
    ingested: list[IngestedObservation],
    after_sequence: int,
    through_sequence: int,
    context_seconds: int,
    captured_at: datetime,
) -> DecisionSnapshot:
    """Describe the batch's new speech in time order, with the speech shortly before it.

    The batch must contain new speech, which is everything after `after_sequence`.
    """
    batch = [row for row in ingested if row.sequence <= through_sequence]
    new = [row.observation for row in batch if row.sequence > after_sequence]
    cutoff = min(row.start_at for row in new) - timedelta(seconds=context_seconds)
    context = sorted(
        (
            row.observation
            for row in batch
            if row.sequence > after_sequence or row.observation.end_at > cutoff
        ),
        key=lambda row: (row.start_at, row.end_at, row.observation_id),
    )
    new_ids = {row.observation_id for row in new}
    return DecisionSnapshot(
        case_id=case_id,
        target_speaker_id=target_speaker_id,
        target_revision=target_revision,
        after_sequence=after_sequence,
        through_sequence=through_sequence,
        captured_at=captured_at,
        observations=context,
        new_observation_ids=[
            row.observation_id for row in context if row.observation_id in new_ids
        ],
    )
