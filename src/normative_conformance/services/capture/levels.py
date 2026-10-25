import math
import struct
from dataclasses import dataclass

SAMPLE_RATE = 16_000
FRAME_SAMPLES = 320  # 20 ms
FRAME_BYTES = FRAME_SAMPLES * 2


@dataclass(frozen=True)
class FrameLevel:
    start_ms: float
    end_ms: float
    dbfs: float


class LevelMeter:
    def __init__(self) -> None:
        self._pending = bytearray()
        self._samples = 0

    def feed(self, *, pcm: bytes) -> list[FrameLevel]:
        if not pcm or len(pcm) % 2:
            raise ValueError("Audio must contain complete PCM16 samples")
        self._pending.extend(pcm)
        frames = []
        while len(self._pending) >= FRAME_BYTES:
            frames.append(self._measure(bytes(self._pending[:FRAME_BYTES])))
            del self._pending[:FRAME_BYTES]
        return frames

    def finish(self) -> list[FrameLevel]:
        """Measure the final partial frame without padding it with silence."""
        if not self._pending:
            return []
        frame = self._measure(bytes(self._pending))
        self._pending.clear()
        return [frame]

    def _measure(self, pcm: bytes) -> FrameLevel:
        count = len(pcm) // 2
        samples = struct.unpack(f"<{count}h", pcm)
        mean_square = math.fsum(sample * sample for sample in samples) / count
        dbfs = max(-120.0, 10 * math.log10(mean_square / 32768**2)) if mean_square else -120.0
        start = self._samples
        self._samples += count
        return FrameLevel(
            start_ms=start * 1000 / SAMPLE_RATE,
            end_ms=self._samples * 1000 / SAMPLE_RATE,
            dbfs=dbfs,
        )
