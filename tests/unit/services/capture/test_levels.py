import math
import struct

import pytest

from normative_conformance.services.capture.levels import FrameLevel
from normative_conformance.services.capture.levels import LevelMeter


@pytest.mark.parametrize(
    "sample,expected",
    [
        (0, -120),
        (-32768, 0),
        (32767, 20 * math.log10(32767 / 32768)),
        (16384, 20 * math.log10(0.5)),
        (-16384, 20 * math.log10(0.5)),
        (1, 20 * math.log10(1 / 32768)),
    ],
)
def test_pcm_amplitudes_have_expected_dbfs(sample, expected):
    meter = LevelMeter()
    frames = meter.feed(pcm=struct.pack("<320h", *([sample] * 320)))
    assert len(frames) == 1
    assert frames[0].start_ms == 0
    assert frames[0].end_ms == 20
    assert frames[0].dbfs == pytest.approx(expected)
    assert meter.finish() == []


def test_rms_uses_squared_samples_without_overflow_or_dc_subtraction():
    meter = LevelMeter()
    pcm = struct.pack("<320h", *([-32768, 0] * 160))
    assert meter.feed(pcm=pcm)[0].dbfs == pytest.approx(10 * math.log10(0.5))


def test_frame_boundaries_are_independent_of_message_boundaries():
    meter = LevelMeter()
    assert meter.feed(pcm=struct.pack("<100h", *([0] * 100))) == []
    frames = meter.feed(pcm=struct.pack("<540h", *([0] * 220 + [-32768] * 320)))
    assert frames == [FrameLevel(0, 20, -120), FrameLevel(20, 40, 0)]
    assert meter.feed(pcm=struct.pack("<80h", *([16384] * 80))) == []
    tail = meter.finish()
    assert len(tail) == 1
    assert (tail[0].start_ms, tail[0].end_ms) == (40, 45)
    assert tail[0].dbfs == pytest.approx(20 * math.log10(0.5))
    assert meter.finish() == []


@pytest.mark.parametrize("pcm", [b"", b"\x01", b"\x00\x01\x02"])
def test_invalid_pcm_does_not_change_the_pending_frame(pcm):
    meter = LevelMeter()
    meter.feed(pcm=b"\x00\x80")
    with pytest.raises(ValueError, match="complete PCM16 samples"):
        meter.feed(pcm=pcm)
    assert meter.finish() == [FrameLevel(0, 0.0625, 0)]
