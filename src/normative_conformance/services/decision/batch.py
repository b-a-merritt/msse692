from datetime import datetime
from datetime import timedelta

from normative_conformance.services.observation.load_case_speech import IngestedObservation


def batch_end(
    *,
    ingested: list[IngestedObservation],
    target_speaker_id: str,
    after_sequence: int,
    max_seconds: int,
    max_turns: int,
    idle_seconds: int,
    now: datetime,
) -> int | None:
    """End a batch where the target's turn ends, so that the target's turns are assessed whole.

    A batch also ends after `max_turns` turns, once its speech spans `max_seconds`, or when no
    speech has arrived for `idle_seconds`. `ingested` is in sequence order. Return None while
    the batch is still open.
    """
    new = [row for row in ingested if row.sequence > after_sequence]

    if not new:
        return None

    start = new[0].observation.start_at
    turns = 1

    for row, following in zip(new, [*new[1:], None], strict=True):
        speaker = row.observation.speaker_id
        turn_ended = following is not None and following.observation.speaker_id != speaker
        # Each turn adds its own topic questions, so the turn limit bounds the request size.
        if turn_ended and (speaker == target_speaker_id or turns == max_turns):
            return row.sequence

        if row.observation.end_at - start >= timedelta(seconds=max_seconds):
            return row.sequence

        turns += turn_ended

    if now - new[-1].received_at >= timedelta(seconds=idle_seconds):
        return new[-1].sequence

    return None
