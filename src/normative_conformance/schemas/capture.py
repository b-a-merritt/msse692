from typing import Literal
from typing import TypedDict


class ReadyMessage(TypedDict):
    type: Literal["ready"]
    sample_rate: int
    encoding: Literal["pcm_s16le"]
    channels: Literal[1]


class FrameLevelPayload(TypedDict):
    start_ms: float
    end_ms: float
    dbfs: float


class LevelsMessage(TypedDict):
    type: Literal["levels"]
    frames: list[FrameLevelPayload]


class StoppedMessage(TypedDict):
    type: Literal["stopped"]


class ErrorMessage(TypedDict):
    type: Literal["error"]
    message: str
