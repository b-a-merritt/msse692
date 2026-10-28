import asyncio
import logging
from datetime import UTC
from datetime import datetime
from functools import partial
from unittest.mock import AsyncMock

import pytest

from normative_conformance.errors import CaptureFailure
from normative_conformance.services.capture import record_transcripts as module
from normative_conformance.services.capture.levels import FrameLevel
from normative_conformance.services.capture.observations import build_observations
from normative_conformance.services.capture.transcriber import SpeakerRevised
from normative_conformance.services.capture.transcriber import TurnRevision
from normative_conformance.services.capture.transcriber import TurnUpdate
from normative_conformance.services.capture.transcriber import Word


class FakeTranscriber:
    """Yield the events the provider would send, then end."""

    session_id = "session-123"

    def __init__(self, *events):
        self._events = events

    async def events(self):
        for event in self._events:
            yield event


def record(*events, started_at, frames, send, store_observations, store_revisions):
    """Record events from a capture whose browser has already stopped."""
    stopping = asyncio.Event()
    stopping.set()
    asyncio.run(
        module.record_transcripts(
            transcriber=FakeTranscriber(*events),
            build=partial(
                build_observations,
                case_id="case",
                session_id="session-123",
                started_at=started_at,
                frames=frames,
            ),
            send=send,
            stopping=stopping,
            capture_id="capture",
            store_observations=store_observations,
            store_revisions=store_revisions,
        )
    )


def test_partial_log_is_once_per_turn_but_every_update_reaches_browser(caplog):
    # Assert diagnostic throttling directly; all transcript updates must still be delivered.
    caplog.set_level(logging.INFO, logger=module.__name__)
    sent = []

    async def send(message):
        sent.append(message)

    record(
        TurnUpdate(turn_order=0, final=False, speaker_id=None, transcript="Hi", words=()),
        TurnUpdate(turn_order=0, final=False, speaker_id=None, transcript="Hi there", words=()),
        TurnUpdate(
            turn_order=0,
            final=True,
            speaker_id=None,
            transcript="Hi there.",
            words=(Word(text="Hi there.", start_ms=0, end_ms=20, speaker_id=None),),
        ),
        TurnUpdate(turn_order=1, final=False, speaker_id=None, transcript="Yes", words=()),
        started_at=datetime(2026, 10, 26, tzinfo=UTC),
        frames=[FrameLevel(start_ms=0, end_ms=20, dbfs=-30)],
        send=send,
        store_observations=AsyncMock(),
        store_revisions=AsyncMock(),
    )

    assert [m["transcript"] for m in sent] == ["Hi", "Hi there", "Hi there.", "Yes"]
    records = [r for r in caplog.records if r.name == module.__name__]
    assert [(r.turn_order, r.final) for r in records] == [(0, False), (0, True), (1, False)]


def test_persists_final_turn_once_before_reporting_it():
    final = TurnUpdate(0, True, "A", "Hello", (Word("Hello", 0, 100, "A"),))
    sent = []
    saved = []

    async def store(observations):
        saved.extend(observations)

    async def send(message):
        assert len(saved) == 1
        sent.append(message)

    record(
        final,
        final,
        started_at=datetime(2026, 10, 26, tzinfo=UTC),
        frames=[FrameLevel(start_ms=0, end_ms=100, dbfs=-120)],
        send=send,
        store_observations=store,
        store_revisions=AsyncMock(),
    )

    assert [m["transcript"] for m in sent] == ["Hello"]
    assert saved[0].speaker_id == "A"
    assert saved[0].transcript == "Hello"
    assert saved[0].signal_level_avg == -120
    assert saved[0].start_at == datetime(2026, 10, 26, tzinfo=UTC)


def test_storage_failure_sends_no_transcript():
    send = AsyncMock()
    with pytest.raises(CaptureFailure) as caught:
        record(
            TurnUpdate(0, True, "A", "Hello", (Word("Hello", 0, 100, "A"),)),
            started_at=datetime(2026, 10, 26, tzinfo=UTC),
            frames=[FrameLevel(start_ms=0, end_ms=100, dbfs=-120)],
            send=send,
            store_observations=AsyncMock(side_effect=CaptureFailure("storageUnavailable")),
            store_revisions=AsyncMock(),
        )
    assert caught.value.code == "storageUnavailable"
    send.assert_not_awaited()


def test_later_final_words_do_not_overwrite_or_represent_unsaved_speech():
    saved = []
    sent = []

    async def store(observations):
        saved.extend(observations)

    async def send(message):
        sent.append(message)

    record(
        TurnUpdate(0, True, "A", "Hello", (Word("Hello", 0, 100, "A"),)),
        TurnUpdate(0, True, "B", "Hello", (Word("Hello", 0, 100, "B"),)),
        started_at=datetime(2026, 10, 26, tzinfo=UTC),
        frames=[FrameLevel(start_ms=0, end_ms=100, dbfs=-120)],
        send=send,
        store_observations=store,
        store_revisions=AsyncMock(),
    )

    assert [(row.speaker_id, row.transcript) for row in saved] == [("A", "Hello")]
    assert [message["speaker_id"] for message in sent] == ["A"]


def test_revisions_commit_before_revised_messages():
    stored = []
    sent = []
    observations = AsyncMock()

    async def store(replacements):
        stored.extend(replacements)

    async def send(message):
        if message["revised"]:
            assert len(stored) == 1
            assert stored[0].observations[0].speaker_id == "B"
        sent.append(message)

    record(
        TurnUpdate(1, True, "A", "Hello", (Word("Hello", 0, 20, "A"),)),
        SpeakerRevised((TurnRevision(1, "B", (Word("Hello", 0, 20, "B"),)),)),
        started_at=datetime(2026, 10, 26, tzinfo=UTC),
        frames=[FrameLevel(start_ms=0, end_ms=20, dbfs=-120)],
        send=send,
        store_observations=observations,
        store_revisions=store,
    )

    original_id = observations.await_args.args[0][0].observation_id
    assert stored[0].replaced_observation_ids == [original_id]
    assert [m["revised"] for m in sent] == [False, True]
    observations.assert_awaited_once()


def test_revision_storage_failure_sends_no_revision():
    sent = []
    observations = AsyncMock()

    async def send(message):
        sent.append(message)

    with pytest.raises(CaptureFailure) as caught:
        record(
            TurnUpdate(1, True, "A", "Hello", (Word("Hello", 0, 20, "A"),)),
            SpeakerRevised((TurnRevision(1, "B", (Word("Hello", 0, 20, "B"),)),)),
            started_at=datetime(2026, 10, 26, tzinfo=UTC),
            frames=[FrameLevel(start_ms=0, end_ms=20, dbfs=-120)],
            send=send,
            store_observations=observations,
            store_revisions=AsyncMock(side_effect=CaptureFailure("storageUnavailable")),
        )
    assert caught.value.code == "storageUnavailable"
    assert [m["revised"] for m in sent] == [False]
    observations.assert_awaited_once()


def test_successive_revisions_regroup_with_utc_times_and_keep_original_links():
    loud = -6.020599913279624
    originals = []
    revisions = []

    async def store_observations(rows):
        originals.extend(rows)

    async def store_revisions(replacements):
        revisions.extend(replacements)

    record(
        TurnUpdate(
            0, True, "A", "Hello there", (Word("Hello", 0, 40, "A"), Word("there", 40, 100, "A"))
        ),
        SpeakerRevised(
            (TurnRevision(0, "A", (Word("Hello", 0, 40, "A"), Word("there", 40, 100, None))),)
        ),
        SpeakerRevised(
            (TurnRevision(0, "B", (Word("Hello", 0, 40, "B"), Word("there", 40, 100, "B"))),)
        ),
        started_at=datetime(2026, 10, 26, 12, tzinfo=UTC),
        frames=[
            FrameLevel(start_ms=0, end_ms=20, dbfs=-120),
            FrameLevel(start_ms=20, end_ms=40, dbfs=-120),
            FrameLevel(start_ms=40, end_ms=60, dbfs=loud),
            FrameLevel(start_ms=60, end_ms=80, dbfs=loud),
            FrameLevel(start_ms=80, end_ms=100, dbfs=loud),
        ],
        send=AsyncMock(),
        store_observations=store_observations,
        store_revisions=store_revisions,
    )

    assert len(originals) == 1
    assert [r.replaced_observation_ids for r in revisions] == [[originals[0].observation_id]] * 2
    assert [r.speaker_id for r in revisions[0].observations] == ["A", "PENDING"]
    assert [r.transcript for r in revisions[0].observations] == ["Hello", "there"]
    assert revisions[0].observations[0].signal_level_avg == -120
    assert revisions[0].observations[1].signal_level_avg == pytest.approx(loud)
    assert revisions[0].observations[0].start_at == datetime(2026, 10, 26, 12, tzinfo=UTC)
    assert revisions[0].observations[1].start_at == datetime(
        2026, 10, 26, 12, 0, 0, 40000, tzinfo=UTC
    )
    assert revisions[1].observations[0].end_at == datetime(
        2026, 10, 26, 12, 0, 0, 100000, tzinfo=UTC
    )
    assert [r.transcript for r in revisions[1].observations] == ["Hello there"]
    assert revisions[1].observations[0].signal_level_avg == originals[0].signal_level_avg


def test_revision_without_an_original_turn_cannot_create_unlinked_context():
    store = AsyncMock()
    with pytest.raises(CaptureFailure) as caught:
        record(
            SpeakerRevised((TurnRevision(99, "B", (Word("Hello", 0, 20, "B"),)),)),
            started_at=datetime(2026, 10, 26, tzinfo=UTC),
            frames=[FrameLevel(start_ms=0, end_ms=20, dbfs=-120)],
            send=AsyncMock(),
            store_observations=AsyncMock(),
            store_revisions=store,
        )
    assert caught.value.code == "providerProtocol"
    store.assert_not_awaited()


def test_events_ending_before_stop_are_incomplete():
    with pytest.raises(CaptureFailure) as caught:
        asyncio.run(
            module.record_transcripts(
                transcriber=FakeTranscriber(),
                build=partial(
                    build_observations,
                    case_id="case",
                    session_id="session-123",
                    started_at=datetime(2026, 10, 26, tzinfo=UTC),
                    frames=[],
                ),
                send=AsyncMock(),
                stopping=asyncio.Event(),
                capture_id="capture",
                store_observations=AsyncMock(),
                store_revisions=AsyncMock(),
            )
        )
    assert caught.value.code == "incomplete"


def test_final_turn_without_words_is_reported_but_not_stored():
    store = AsyncMock()
    sent = []

    async def send(message):
        sent.append(message)

    record(
        TurnUpdate(0, True, None, "", ()),
        started_at=datetime(2026, 10, 26, tzinfo=UTC),
        frames=[],
        send=send,
        store_observations=store,
        store_revisions=AsyncMock(),
    )

    store.assert_not_awaited()
    assert [(m["turn_order"], m["final"]) for m in sent] == [(0, True)]
