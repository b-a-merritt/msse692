from datetime import datetime
from datetime import timedelta

from normative_conformance.services.observation.load_case_speech import IngestedObservation


def batch_end(
    *,
    ingested: list[IngestedObservation],
    target_speaker_id: str,
    after_sequence: int,
    max_seconds: int,
    idle_seconds: int,
    now: datetime,
) -> int | None:
    """End a batch where the target's turn ends, so that the target's turns are assessed whole.

    A batch also ends once its speech spans `max_seconds`, or when no speech has arrived for
    `idle_seconds`. `ingested` is in sequence order. Return None while the batch is still open.
    """
    new = [row for row in ingested if row.sequence > after_sequence]
    if not new:
        return None
    start = new[0].observation.start_at
    for row, following in zip(new, [*new[1:], None], strict=True):
        speaker = row.observation.speaker_id
        turn_ended = (
            speaker == target_speaker_id
            and following is not None
            and following.observation.speaker_id != speaker
        )
        if turn_ended or row.observation.end_at - start >= timedelta(seconds=max_seconds):
            return row.sequence
    if now - new[-1].received_at >= timedelta(seconds=idle_seconds):
        return new[-1].sequence
    return None
