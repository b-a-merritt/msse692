from collections.abc import Awaitable
from collections.abc import Callable
from typing import Literal
from typing import TypedDict


class ReadyMessage(TypedDict):
    type: Literal["ready"]
    case_id: str
    sample_rate: int
    encoding: Literal["pcm_s16le"]
    channels: Literal[1]
    session_id: str
    speech_model: str


class FrameLevelPayload(TypedDict):
    start_ms: float
    end_ms: float
    dbfs: float


class LevelsMessage(TypedDict):
    type: Literal["levels"]
    frames: list[FrameLevelPayload]


class StoppedMessage(TypedDict):
    type: Literal["stopped"]


CaptureErrorCode = Literal[
    "notConfigured",
    "providerAuth",
    "providerUnavailable",
    "providerProtocol",
    "providerTimeout",
    "invalidAudio",
    "incomplete",
    "storageUnavailable",
]


class WordPayload(TypedDict):
    text: str
    start_ms: int
    end_ms: int
    speaker_id: str | None


class TranscriptMessage(TypedDict):
    type: Literal["transcript"]
    turn_order: int
    final: bool
    revised: bool
    transcript: str
    speaker_id: str | None
    words: list[WordPayload]


class ErrorMessage(TypedDict):
    type: Literal["error"]
    code: CaptureErrorCode
    message: str


OutgoingMessage = ReadyMessage | LevelsMessage | TranscriptMessage | StoppedMessage
Send = Callable[[OutgoingMessage], Awaitable[None]]
