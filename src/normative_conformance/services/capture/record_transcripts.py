import asyncio
import logging
from collections.abc import Awaitable
from collections.abc import Callable
from typing import Protocol

from normative_conformance.errors import CaptureFailure
from normative_conformance.schemas.capture import Send
from normative_conformance.schemas.capture import TranscriptMessage
from normative_conformance.schemas.capture import WordPayload
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.schemas.observation import ObservationReplacement
from normative_conformance.services.capture.transcriber import SpeakerRevised
from normative_conformance.services.capture.transcriber import Transcriber
from normative_conformance.services.capture.transcriber import TurnRevision
from normative_conformance.services.capture.transcriber import TurnUpdate

logger = logging.getLogger(__name__)

StoreObservations = Callable[[list[ObservationInput]], Awaitable[None]]
StoreRevisions = Callable[[list[ObservationReplacement]], Awaitable[None]]


class BuildObservations(Protocol):
    def __call__(self, *, turn: TurnUpdate) -> list[ObservationInput]: ...


async def record_transcripts(
    *,
    transcriber: Transcriber,
    build: BuildObservations,
    send: Send,
    stopping: asyncio.Event,
    capture_id: str,
    store_observations: StoreObservations,
    store_revisions: StoreRevisions,
) -> None:
    """Store each final turn and revision before echoing it to the browser, until events end.

    Raises `CaptureFailure` when events end before the browser stopped.
    """
    # Each stored turn's observation IDs, which its revisions replace.
    stored: dict[int, list[str]] = {}
    last_partial_turn: int | None = None
    async for event in transcriber.events():
        if isinstance(event, TurnUpdate):
            # A turn's first final is saved; later finals for it are ignored.
            if event.final and event.turn_order in stored:
                continue
            if event.final:
                await _store_final(turn=event, build=build, stored=stored, store=store_observations)
            if event.final or event.turn_order != last_partial_turn:
                _log_transcript(turn=event, capture_id=capture_id)
                last_partial_turn = event.turn_order
            await send(_transcript_message(turn=event, revised=False))
        elif isinstance(event, SpeakerRevised):
            await _record_revision(
                revision=event,
                build=build,
                stored=stored,
                send=send,
                capture_id=capture_id,
                store=store_revisions,
            )
        else:
            logger.info(
                "Speech detected by transcription service",
                extra={"event": "capture.speech_started", "capture_id": capture_id},
            )
    if not stopping.is_set():
        raise CaptureFailure("incomplete")


async def _store_final(
    *,
    turn: TurnUpdate,
    build: BuildObservations,
    stored: dict[int, list[str]],
    store: StoreObservations,
) -> None:
    observations = build(turn=turn)
    if observations:
        await store(observations)
        stored[turn.turn_order] = [row.observation_id for row in observations]


async def _record_revision(
    *,
    revision: SpeakerRevised,
    build: BuildObservations,
    stored: dict[int, list[str]],
    send: Send,
    capture_id: str,
    store: StoreRevisions,
) -> None:
    turns = [_final_turn(turn) for turn in revision.turns]
    await store(
        [
            ObservationReplacement(
                replaced_observation_ids=_replaced_ids(stored=stored, turn_order=turn.turn_order),
                observations=build(turn=turn),
            )
            for turn in turns
        ]
    )
    logger.info(
        "Speaker revisions received",
        extra={
            "event": "capture.speaker_revisions",
            "capture_id": capture_id,
            "turn_orders": [turn.turn_order for turn in turns],
        },
    )
    for turn in turns:
        await send(_transcript_message(turn=turn, revised=True))


def _log_transcript(*, turn: TurnUpdate, capture_id: str) -> None:
    logger.info(
        "Final transcript received" if turn.final else "Partial transcript received",
        extra={
            "event": "capture.transcript_received",
            "capture_id": capture_id,
            "turn_order": turn.turn_order,
            "final": turn.final,
            "speaker_id": turn.speaker_id,
            "word_count": len(turn.words),
            "character_count": len(turn.transcript),
        },
    )


def _final_turn(revision: TurnRevision) -> TurnUpdate:
    return TurnUpdate(
        turn_order=revision.turn_order,
        final=True,
        speaker_id=revision.speaker_id,
        transcript=" ".join(w.text for w in revision.words),
        words=revision.words,
    )


def _replaced_ids(*, stored: dict[int, list[str]], turn_order: int) -> list[str]:
    """A revision may only replace a turn this capture has stored."""
    if turn_order not in stored:
        raise CaptureFailure("providerProtocol")
    return stored[turn_order]


def _transcript_message(*, turn: TurnUpdate, revised: bool) -> TranscriptMessage:
    return TranscriptMessage(
        type="transcript",
        turn_order=turn.turn_order,
        final=turn.final,
        revised=revised,
        transcript=turn.transcript,
        speaker_id=turn.speaker_id,
        words=[
            WordPayload(text=w.text, start_ms=w.start_ms, end_ms=w.end_ms, speaker_id=w.speaker_id)
            for w in turn.words
        ],
    )
