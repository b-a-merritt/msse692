from normative_conformance.services.capture.levels import SAMPLE_RATE

BYTES_PER_SAMPLE = 2
MIN_PACKET_BYTES = SAMPLE_RATE * BYTES_PER_SAMPLE * 50 // 1000  # 50 ms
FORWARD_PACKET_BYTES = SAMPLE_RATE * BYTES_PER_SAMPLE * 100 // 1000  # 100 ms


class PCMBuffer:
    """Keep a 50 ms tail so provider packets stay within 50-1000 ms without padding."""

    def __init__(self) -> None:
        self._pending = bytearray()

    def feed(self, pcm: bytes) -> bytes:
        if not pcm or len(pcm) > FORWARD_PACKET_BYTES or len(pcm) % BYTES_PER_SAMPLE:
            raise ValueError("Send 1-1600 PCM16 samples per binary message")
        self._pending.extend(pcm)
        if len(self._pending) < FORWARD_PACKET_BYTES + MIN_PACKET_BYTES:
            return b""
        packet = bytes(self._pending[:FORWARD_PACKET_BYTES])
        del self._pending[:FORWARD_PACKET_BYTES]
        return packet

    def finish(self) -> bytes:
        if 0 < len(self._pending) < MIN_PACKET_BYTES:
            raise ValueError("Record at least 50 ms of audio")
        packet = bytes(self._pending)
        self._pending.clear()
        return packet
