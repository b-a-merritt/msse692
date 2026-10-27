import json
from datetime import datetime
from datetime import timedelta
from itertools import groupby
from math import fsum
from uuid import NAMESPACE_URL
from uuid import uuid5

from pydantic import ValidationError

from normative_conformance.errors import CaptureFailure
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.services.capture.levels import FrameLevel
from normative_conformance.services.capture.transcriber import TurnUpdate
from normative_conformance.services.capture.transcriber import Word


def build_observations(
    *,
    case_id: str,
    session_id: str,
    started_at: datetime,
    frames: list[FrameLevel],
    turn: TurnUpdate,
) -> list[ObservationInput]:
    """Convert finalized words to speaker runs without changing the supplied inputs."""
    if not turn.final:
        return []

    if not turn.words:
        if turn.transcript.strip():
            raise CaptureFailure("providerProtocol")
        return []

    try:
        return [
            _observation(
                case_id=case_id,
                session_id=session_id,
                started_at=started_at,
                frames=frames,
                turn_order=turn.turn_order,
                label=label,
                run=list(indexed_words),
            )
            for label, indexed_words in groupby(
                enumerate(turn.words), key=lambda item: item[1].speaker_id or "PENDING"
            )
        ]
    except (ValidationError, OverflowError) as error:
        raise CaptureFailure("providerProtocol") from error


def _observation(
    *,
    case_id: str,
    session_id: str,
    started_at: datetime,
    frames: list[FrameLevel],
    turn_order: int,
    label: str,
    run: list[tuple[int, Word]],
) -> ObservationInput:
    start = run[0][1].start_ms
    end = run[-1][1].end_ms
    levels = [f.dbfs for f in frames if f.start_ms < end and f.end_ms > start]

    if not levels or any(w.end_ms < w.start_ms for _, w in run):
        raise CaptureFailure("providerProtocol")

    identity = json.dumps([session_id, turn_order, run[0][0], run[-1][0], label])
    return ObservationInput(
        case_id=case_id,
        observation_id=str(uuid5(NAMESPACE_URL, identity)),
        speaker_id=label,
        start_at=started_at + timedelta(milliseconds=start),
        end_at=started_at + timedelta(milliseconds=end),
        transcript=" ".join(w.text for _, w in run),
        signal_level_min=min(levels),
        signal_level_avg=fsum(levels) / len(levels),
        signal_level_max=max(levels),
    )
