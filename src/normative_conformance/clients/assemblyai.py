"""AssemblyAI streaming transcription behind the capture `Transcriber` interface."""

import asyncio
from collections.abc import AsyncIterator
from collections.abc import Iterator
from contextlib import asynccontextmanager
from contextlib import contextmanager
from contextlib import suppress
from typing import Annotated
from typing import Literal
from urllib.parse import urlencode

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import TypeAdapter
from pydantic import ValidationError
from websockets.asyncio.client import ClientConnection
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus
from websockets.exceptions import WebSocketException

from normative_conformance.errors import CaptureFailure
from normative_conformance.schemas.capture import CaptureErrorCode
from normative_conformance.services.capture.levels import SAMPLE_RATE
from normative_conformance.services.capture.transcriber import SpeakerRevised
from normative_conformance.services.capture.transcriber import SpeechStarted
from normative_conformance.services.capture.transcriber import TranscriptEvent
from normative_conformance.services.capture.transcriber import TurnRevision
from normative_conformance.services.capture.transcriber import TurnUpdate
from normative_conformance.services.capture.transcriber import Word

SPEECH_MODEL = "universal-3-6-pro"
PROVIDER_URL = "wss://streaming.assemblyai.com/v3/ws?" + urlencode(
    {
        "sample_rate": SAMPLE_RATE,
        "encoding": "pcm_s16le",
        "speech_model": SPEECH_MODEL,
        "speaker_labels": "true",
        "filter_profanity": "false",
        "speaker_labels_revision_interval_ms": 300000,
    }
)
PROVIDER_TIMEOUT = 10
TERMINATE = '{"type":"Terminate"}'


# Fields consumed from AssemblyAI's streaming events; other fields are ignored.
class ProviderModel(BaseModel):
    model_config = ConfigDict(strict=True)


class Begin(ProviderModel):
    type: Literal["Begin"]
    id: str = Field(min_length=1)


class ProviderWord(ProviderModel):
    text: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    speaker: str | None = None


class Revision(ProviderModel):
    turn_order: int = Field(ge=0)
    speaker_label: str | None = None
    words: list[ProviderWord]


class Turn(Revision):
    type: Literal["Turn"]
    end_of_turn: bool
    transcript: str


class SpeakerRevision(ProviderModel):
    type: Literal["SpeakerRevision"]
    revisions: list[Revision]


class Termination(ProviderModel):
    type: Literal["Termination"]


class InformationalEvent(ProviderModel):
    type: Literal["SpeechStarted", "Heartbeat"]


STREAM_EVENT: TypeAdapter[Turn | SpeakerRevision | Termination | InformationalEvent] = TypeAdapter(
    Annotated[
        Turn | SpeakerRevision | Termination | InformationalEvent, Field(discriminator="type")
    ]
)


@contextmanager
def _provider_errors() -> Iterator[None]:
    """Map provider failures to fixed codes; raw errors may contain headers or bodies."""
    try:
        yield
    except ValidationError as error:
        raise CaptureFailure("providerProtocol") from error
    except TimeoutError as error:
        raise CaptureFailure("providerTimeout") from error
    except InvalidStatus as error:
        code: CaptureErrorCode = (
            "providerAuth" if error.response.status_code in (401, 403) else "providerUnavailable"
        )
        raise CaptureFailure(code) from error
    except (OSError, WebSocketException) as error:
        raise CaptureFailure("providerUnavailable") from error


def _words(words: list[ProviderWord]) -> tuple[Word, ...]:
    return tuple(
        Word(
            text=w.text,
            start_ms=w.start,
            end_ms=w.end,
            speaker_id=w.speaker,
        )
        for w in words
    )


class AssemblyAITranscriber:
    speech_model = SPEECH_MODEL

    def __init__(self, *, connection: ClientConnection, session_id: str) -> None:
        self._connection = connection
        self.session_id = session_id
        self.finished = False

    async def send_audio(self, pcm: bytes) -> None:
        with _provider_errors():
            await asyncio.wait_for(
                self._connection.send(pcm),
                timeout=PROVIDER_TIMEOUT,
            )

    async def finish(self) -> None:
        self.finished = True
        with _provider_errors():
            await asyncio.wait_for(
                self._connection.send(TERMINATE),
                timeout=PROVIDER_TIMEOUT,
            )

    async def events(self) -> AsyncIterator[TranscriptEvent]:
        """Yield transcript events until `Termination`; heartbeats are dropped."""
        while True:
            with _provider_errors():
                event = STREAM_EVENT.validate_json(await self._connection.recv())
            if isinstance(event, Turn):
                yield TurnUpdate(
                    turn_order=event.turn_order,
                    final=event.end_of_turn,
                    speaker_id=event.speaker_label,
                    transcript=event.transcript,
                    words=_words(event.words),
                )
            elif isinstance(event, SpeakerRevision):
                yield SpeakerRevised(
                    turns=tuple(
                        TurnRevision(
                            turn_order=revision.turn_order,
                            speaker_id=revision.speaker_label,
                            words=_words(revision.words),
                        )
                        for revision in event.revisions
                    )
                )
            elif isinstance(event, Termination):
                return
            elif event.type == "SpeechStarted":
                yield SpeechStarted()


@asynccontextmanager
async def connect_transcriber(*, api_key: str) -> AsyncIterator[AssemblyAITranscriber]:
    """Open a session after `Begin`; on exit, terminate it unless `finish()` already did."""
    if not api_key.strip():
        raise CaptureFailure("notConfigured")
    with _provider_errors():
        connection = await connect(
            PROVIDER_URL,
            additional_headers={"Authorization": api_key},
            open_timeout=PROVIDER_TIMEOUT,
            close_timeout=2,
            max_size=1_048_576,
            max_queue=16,
        )
    transcriber: AssemblyAITranscriber | None = None
    try:
        with _provider_errors():
            begin = Begin.model_validate_json(
                await asyncio.wait_for(
                    connection.recv(),
                    timeout=PROVIDER_TIMEOUT,
                )
            )
        transcriber = AssemblyAITranscriber(
            connection=connection,
            session_id=begin.id,
        )
        yield transcriber
    finally:
        if transcriber is None or not transcriber.finished:
            with suppress(OSError, WebSocketException, TimeoutError):
                await asyncio.wait_for(connection.send(TERMINATE), timeout=1)
        await connection.close()
