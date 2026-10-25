import pytest

from normative_conformance.services.capture.pcm import PCMBuffer


def test_repacketizes_without_changing_or_padding_samples():
    buffer = PCMBuffer()
    first, second, tail = b"\x01\x02" * 1600, b"\x03\x04" * 1600, b"\x05\x06" * 80
    assert buffer.feed(first) == b""
    assert buffer.feed(second) == first
    assert buffer.feed(tail) == b""
    assert buffer.finish() == second + tail
    assert buffer.finish() == b""


def test_small_browser_messages_accumulate_into_valid_provider_packets():
    buffer = PCMBuffer()
    assert buffer.feed(b"\x00\x00" * 800) == b""
    assert buffer.finish() == b"\x00\x00" * 800


@pytest.mark.parametrize("packet", [b"", b"\x01", b"\x00" * 3202])
def test_invalid_input_does_not_change_buffer(packet):
    buffer = PCMBuffer()
    buffer.feed(b"\x00\x00" * 1600)
    with pytest.raises(ValueError):
        buffer.feed(packet)
    assert buffer.finish() == b"\x00\x00" * 1600


def test_rejects_a_capture_shorter_than_provider_minimum():
    buffer = PCMBuffer()
    buffer.feed(b"\x00\x00" * 799)
    with pytest.raises(ValueError, match="at least 50 ms"):
        buffer.finish()
