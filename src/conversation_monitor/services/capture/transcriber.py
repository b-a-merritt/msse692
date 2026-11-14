from collections.abc import AsyncIterator
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Word:
    """Offsets are milliseconds from the first audio sample sent to the session.

    `speaker_id` is None when the provider has not attributed the word.
    """

    text: str
    start_ms: int
    end_ms: int
    speaker_id: str | None


@dataclass(frozen=True)
class TurnUpdate:
    """A partial or final transcript for one provider turn; `speaker_id` is None if unattributed."""

    turn_order: int
    final: bool
    speaker_id: str | None
    transcript: str
    words: tuple[Word, ...]


@dataclass(frozen=True)
class TurnRevision:
    """Corrected speaker attribution for an already finalized turn."""

    turn_order: int
    speaker_id: str | None
    words: tuple[Word, ...]


@dataclass(frozen=True)
class SpeakerRevised:
    turns: tuple[TurnRevision, ...]


@dataclass(frozen=True)
class SpeechStarted:
    pass


TranscriptEvent = TurnUpdate | SpeakerRevised | SpeechStarted


class Transcriber(Protocol):
    """An open transcription session. Implementations raise `CaptureFailure` on provider errors."""

    @property
    def session_id(self) -> str: ...

    @property
    def speech_model(self) -> str: ...

    async def send_audio(self, pcm: bytes) -> None: ...

    async def finish(self) -> None:
        """Request the final transcripts; `events()` ends once the provider has sent them."""

    def events(self) -> AsyncIterator[TranscriptEvent]: ...


ConnectTranscriber = Callable[[], AbstractAsyncContextManager[Transcriber]]
