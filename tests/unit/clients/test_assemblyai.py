import asyncio
import json
from unittest.mock import AsyncMock
from urllib.parse import parse_qs
from urllib.parse import urlsplit

import pytest
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosedError
from websockets.exceptions import InvalidStatus
from websockets.http11 import Response

from normative_conformance.clients import assemblyai as module
from normative_conformance.errors import CaptureFailure
from normative_conformance.services.capture.transcriber import SpeakerRevised
from normative_conformance.services.capture.transcriber import SpeechStarted
from normative_conformance.services.capture.transcriber import TurnRevision
from normative_conformance.services.capture.transcriber import TurnUpdate
from normative_conformance.services.capture.transcriber import Word

BEGIN = '{"type":"Begin","id":"session-123"}'


def connect_double(monkeypatch, provider):
    """Supply only the connection; each test defines what the provider sends."""
    connect = AsyncMock(return_value=provider)
    monkeypatch.setattr(module, "connect", connect)
    return connect


def test_opens_session_with_stream_settings_and_terminates_on_exit(monkeypatch):
    provider = AsyncMock()
    provider.recv.return_value = BEGIN
    connect = connect_double(monkeypatch, provider)

    async def scenario():
        async with module.connect_transcriber(api_key="test-key") as transcriber:
            assert transcriber.session_id == "session-123"
            assert transcriber.speech_model == "universal-3-6-pro"
            await transcriber.send_audio(b"\x00\x00")

    asyncio.run(scenario())
    assert connect.call_args.kwargs["additional_headers"] == {"Authorization": "test-key"}
    assert parse_qs(urlsplit(connect.call_args.args[0]).query) == {
        "sample_rate": ["16000"],
        "encoding": ["pcm_s16le"],
        "speech_model": ["universal-3-6-pro"],
        "speaker_labels": ["true"],
        "filter_profanity": ["false"],
        "speaker_labels_revision_interval_ms": ["300000"],
    }
    assert [c.args[0] for c in provider.send.await_args_list] == [b"\x00\x00", module.TERMINATE]
    provider.close.assert_awaited_once()


def test_finish_terminates_once(monkeypatch):
    provider = AsyncMock()
    provider.recv.return_value = BEGIN
    connect_double(monkeypatch, provider)

    async def scenario():
        async with module.connect_transcriber(api_key="test-key") as transcriber:
            await transcriber.finish()

    asyncio.run(scenario())
    provider.send.assert_awaited_once_with(module.TERMINATE)
    provider.close.assert_awaited_once()


def test_missing_key_is_reported_without_connecting(monkeypatch):
    connect = connect_double(monkeypatch, AsyncMock())

    async def scenario():
        async with module.connect_transcriber(api_key=" "):
            pass

    with pytest.raises(CaptureFailure) as caught:
        asyncio.run(scenario())
    assert caught.value.code == "notConfigured"
    connect.assert_not_called()


@pytest.mark.parametrize(
    "failure,expected",
    [
        (OSError("private detail"), "providerUnavailable"),
        (TimeoutError("private detail"), "providerTimeout"),
        (InvalidStatus(Response(401, "Unauthorized", Headers())), "providerAuth"),
        (InvalidStatus(Response(403, "Forbidden", Headers())), "providerAuth"),
        (InvalidStatus(Response(503, "Unavailable", Headers())), "providerUnavailable"),
    ],
)
def test_connection_failures_have_fixed_codes(monkeypatch, failure, expected):
    connect = connect_double(monkeypatch, AsyncMock())
    connect.side_effect = failure

    async def scenario():
        async with module.connect_transcriber(api_key="test-key"):
            pass

    with pytest.raises(CaptureFailure) as caught:
        asyncio.run(scenario())
    assert caught.value.code == expected
    assert "private detail" not in str(caught.value)


@pytest.mark.parametrize("event", ['{"type":"Begin"}', "not json"])
def test_invalid_begin_terminates_and_closes_provider(monkeypatch, event):
    provider = AsyncMock()
    provider.recv.return_value = event
    connect_double(monkeypatch, provider)

    async def scenario():
        async with module.connect_transcriber(api_key="test-key"):
            pass

    with pytest.raises(CaptureFailure) as caught:
        asyncio.run(scenario())
    assert caught.value.code == "providerProtocol"
    provider.send.assert_awaited_once_with(module.TERMINATE)
    provider.close.assert_awaited_once()


def test_events_convert_provider_messages_until_termination(monkeypatch):
    provider = AsyncMock()
    provider.recv.side_effect = [
        BEGIN,
        *[
            json.dumps(event)
            for event in [
                {
                    "type": "Turn",
                    "turn_order": 0,
                    "end_of_turn": False,
                    "transcript": "Hello",
                    "speaker_label": "PENDING",
                    "words": [],
                },
                {"type": "Heartbeat"},
                {"type": "SpeechStarted", "timestamp": 0},
                {
                    "type": "Turn",
                    "turn_order": 0,
                    "end_of_turn": True,
                    "transcript": "Hello there.",
                    "speaker_label": "A",
                    "words": [
                        {"text": "Hello", "start": 0, "end": 60, "speaker": "A"},
                        {"text": "there.", "start": 60, "end": 100},
                    ],
                },
                {
                    "type": "SpeakerRevision",
                    "revisions": [
                        {
                            "turn_order": 0,
                            "speaker_label": "B",
                            "words": [{"text": "Hello", "start": 0, "end": 60, "speaker": "B"}],
                        }
                    ],
                },
                {"type": "Termination"},
            ]
        ],
    ]
    connect_double(monkeypatch, provider)

    async def scenario():
        async with module.connect_transcriber(api_key="test-key") as transcriber:
            return [event async for event in transcriber.events()]

    assert asyncio.run(scenario()) == [
        TurnUpdate(turn_order=0, final=False, speaker_id="PENDING", transcript="Hello", words=()),
        SpeechStarted(),
        TurnUpdate(
            turn_order=0,
            final=True,
            speaker_id="A",
            transcript="Hello there.",
            words=(
                Word(text="Hello", start_ms=0, end_ms=60, speaker_id="A"),
                Word(text="there.", start_ms=60, end_ms=100, speaker_id=None),
            ),
        ),
        SpeakerRevised(
            turns=(
                TurnRevision(
                    turn_order=0,
                    speaker_id="B",
                    words=(Word(text="Hello", start_ms=0, end_ms=60, speaker_id="B"),),
                ),
            )
        ),
    ]


@pytest.mark.parametrize(
    "event,expected",
    [
        ('{"type":"Turn","turn_order":"invalid"}', "providerProtocol"),
        ('{"type":"Unknown"}', "providerProtocol"),
        (ConnectionClosedError(None, None), "providerUnavailable"),
    ],
)
def test_event_failures_have_fixed_codes(monkeypatch, event, expected):
    provider = AsyncMock()
    provider.recv.side_effect = [BEGIN, event]
    connect_double(monkeypatch, provider)

    async def scenario():
        async with module.connect_transcriber(api_key="test-key") as transcriber:
            async for _ in transcriber.events():
                pass

    with pytest.raises(CaptureFailure) as caught:
        asyncio.run(scenario())
    assert caught.value.code == expected
    provider.close.assert_awaited_once()


def test_stalled_audio_send_is_a_provider_timeout(monkeypatch):
    provider = AsyncMock()
    provider.recv.return_value = BEGIN
    connect_double(monkeypatch, provider)

    async def scenario():
        async with module.connect_transcriber(api_key="test-key") as transcriber:
            provider.send.side_effect = TimeoutError()
            await transcriber.send_audio(b"\x00\x00")

    with pytest.raises(CaptureFailure) as caught:
        asyncio.run(scenario())
    assert caught.value.code == "providerTimeout"
