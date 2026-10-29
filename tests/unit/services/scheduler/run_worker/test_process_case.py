from contextlib import contextmanager
from datetime import UTC
from datetime import datetime
from importlib import import_module
from unittest.mock import Mock

import pytest
from httpx2 import Headers
from sqlmodel import Session
from typesafe_sdk import TypeSafeAuthenticationError
from typesafe_sdk import TypeSafeBadRequestError
from typesafe_sdk import TypeSafeInternalServerError
from typesafe_sdk import TypeSafeUnprocessableEntityError

from normative_conformance.schemas.case import CaseRecord
from normative_conformance.schemas.decision import DecisionAnswers
from normative_conformance.schemas.decision import PatternEvidence
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.services.observation.load_case_speech import IngestedObservation

module = import_module("normative_conformance.services.scheduler.run_worker.process_case")


def _ingested(*, observation_id, sequence, speaker_id):
    return IngestedObservation(
        observation_key=sequence * 10,
        sequence=sequence,
        received_at=datetime.fromtimestamp(sequence, UTC),
        observation=ObservationInput(
            case_id="case",
            observation_id=observation_id,
            speaker_id=speaker_id,
            start_at=datetime.fromtimestamp(sequence, UTC),
            end_at=datetime.fromtimestamp(sequence + 0.5, UTC),
            transcript="Hello",
            signal_level_min=-40,
            signal_level_avg=-30,
            signal_level_max=-20,
        ),
    )


def _sessions(*, monkeypatch, reader, writer):
    """Replace both transactions and report which are open."""
    open_transactions = set()

    def opener(name, session):
        @contextmanager
        def open_session(**kwargs):
            open_transactions.add(name)
            try:
                yield session
            finally:
                open_transactions.remove(name)

        return open_session

    monkeypatch.setattr(module, "read_session", opener("read", reader))
    monkeypatch.setattr(module, "write_session", opener("write", writer))
    return open_transactions


ANSWERS = DecisionAnswers(
    model="jev-1.14.0",
    prompt_version="conversation-1",
    observations=[],
    action="await_context",
    action_confidence=1,
    action_probabilities={"await_context": 1},
)
KWARGS = {
    "case_id": "case",
    "engine": object(),
    "client": object(),
    "max_batch_seconds": 60,
    "idle_seconds": 20,
    "context_seconds": 30,
    # Speech is received after this time, so a batch only ends with the target's turn.
    "now": lambda: datetime(1970, 1, 1, tzinfo=UTC),
}


def _case(*, target_speaker_id, target_revision):
    return CaseRecord(
        case_id="case",
        created_at="1970-01-01T00:00:00Z",
        target_speaker_order=None,
        target_speaker_id=target_speaker_id,
        target_revision=target_revision,
    )


@pytest.mark.parametrize(
    "case,handled_through,sequences",
    [
        pytest.param(_case(target_speaker_id=None, target_revision=0), 0, [1], id="no-target"),
        pytest.param(
            _case(target_speaker_id=None, target_revision=1),
            0,
            [1],
            id="unresolved-target",
        ),
        pytest.param(
            _case(target_speaker_id="A", target_revision=1),
            0,
            [],
            id="no-speech",
        ),
        pytest.param(
            _case(target_speaker_id="A", target_revision=1),
            2,
            [1, 2],
            id="handled",
        ),
        pytest.param(
            _case(target_speaker_id="A", target_revision=1),
            0,
            [1, 2],
            id="target-turn-open",
        ),
    ],
)
def test_cases_without_a_closed_batch_for_a_resolved_target_are_skipped(
    monkeypatch, case, handled_through, sequences
):
    writer = Mock(spec=Session)
    _sessions(monkeypatch=monkeypatch, reader=Mock(spec=Session), writer=writer)
    monkeypatch.setattr(module, "get_case", Mock(return_value=case))
    monkeypatch.setattr(module, "read_handled_through", Mock(return_value=handled_through))
    monkeypatch.setattr(
        module,
        "load_case_speech",
        Mock(
            return_value=[
                _ingested(observation_id=str(sequence), sequence=sequence, speaker_id="A")
                for sequence in sequences
            ]
        ),
    )
    evaluate = Mock()
    monkeypatch.setattr(module.jev, "evaluate", evaluate)
    find_evidence = Mock()
    monkeypatch.setattr(module, "find_evidence", find_evidence)
    mark_handled = Mock()
    monkeypatch.setattr(module, "mark_handled", mark_handled)

    assert module.process_case(**KWARGS) is None

    # Evidence is not checked while a batch is still open.
    find_evidence.assert_not_called()
    evaluate.assert_not_called()
    mark_handled.assert_not_called()
    writer.commit.assert_not_called()


def test_snapshot_is_taken_outside_transactions_and_progress_commits_with_the_result(
    monkeypatch,
):
    writer = Mock(spec=Session)
    reader = Mock(spec=Session)
    open_transactions = _sessions(monkeypatch=monkeypatch, reader=reader, writer=writer)
    monkeypatch.setattr(
        module,
        "get_case",
        Mock(return_value=_case(target_speaker_id="A", target_revision=2)),
    )
    monkeypatch.setattr(module, "read_handled_through", Mock(return_value=1))
    monkeypatch.setattr(
        module,
        "load_case_speech",
        Mock(
            return_value=[
                _ingested(observation_id="one", sequence=1, speaker_id="A"),
                _ingested(observation_id="two", sequence=2, speaker_id="A"),
                _ingested(observation_id="three", sequence=3, speaker_id="B"),
            ]
        ),
    )
    snapshots = []
    found = PatternEvidence(normative_model_id=3, topics=["budgeting"])
    find_evidence = Mock(return_value=found)
    monkeypatch.setattr(module, "find_evidence", find_evidence)

    def evaluate(*, snapshot, evidence, client):
        assert open_transactions == set()
        assert evidence is found
        snapshots.append(snapshot)
        return ANSWERS, '{"state":{}}'

    monkeypatch.setattr(module.jev, "evaluate", evaluate)
    store = Mock(return_value=9)
    monkeypatch.setattr(module, "store_assessment", store)
    create = Mock()
    monkeypatch.setattr(module, "create_intervention", create)
    mark_handled = Mock()
    monkeypatch.setattr(module, "mark_handled", mark_handled)

    assert module.process_case(**KWARGS) == 9

    [snapshot] = snapshots
    find_evidence.assert_called_once_with(case_id="case", target_revision=2, session=reader)
    assert (snapshot.target_speaker_id, snapshot.target_revision) == ("A", 2)
    assert (snapshot.after_sequence, snapshot.through_sequence) == (1, 2)
    assert store.call_args.kwargs["snapshot"] is snapshot
    assert store.call_args.kwargs["answers"] is ANSWERS
    assert store.call_args.kwargs["observation_keys"] == {"one": 10, "two": 20, "three": 30}
    create.assert_called_once_with(
        assessment_id=9,
        created_at_us=store.call_args.kwargs["completed_at_us"],
        answers=ANSWERS,
        session=writer,
    )
    mark_handled.assert_called_once_with(
        case_id="case", target_revision=2, through_sequence=2, session=writer
    )
    writer.commit.assert_called_once()


@pytest.mark.parametrize(
    "provider_error,storage_error",
    [
        pytest.param(TypeSafeInternalServerError(500, {}, Headers()), None, id="provider-outage"),
        pytest.param(TypeSafeAuthenticationError(401, {}, Headers()), None, id="invalid-key"),
        pytest.param(None, RuntimeError("Disk failed"), id="storage"),
    ],
)
def test_failures_leave_progress_unchanged(monkeypatch, provider_error, storage_error):
    writer = Mock(spec=Session)
    _sessions(monkeypatch=monkeypatch, reader=Mock(spec=Session), writer=writer)
    monkeypatch.setattr(
        module,
        "get_case",
        Mock(return_value=_case(target_speaker_id="A", target_revision=2)),
    )
    monkeypatch.setattr(module, "read_handled_through", Mock(return_value=0))
    monkeypatch.setattr(
        module,
        "load_case_speech",
        Mock(
            return_value=[
                _ingested(observation_id="one", sequence=1, speaker_id="A"),
                _ingested(observation_id="two", sequence=2, speaker_id="B"),
            ]
        ),
    )
    monkeypatch.setattr(module, "find_evidence", Mock(return_value=None))
    monkeypatch.setattr(
        module.jev, "evaluate", Mock(return_value=(ANSWERS, "{}"), side_effect=provider_error)
    )
    monkeypatch.setattr(module, "store_assessment", Mock(side_effect=storage_error))
    mark_handled = Mock()
    monkeypatch.setattr(module, "mark_handled", mark_handled)

    with pytest.raises(Exception) as caught:
        module.process_case(**KWARGS)

    assert caught.value is (provider_error or storage_error)
    mark_handled.assert_not_called()
    writer.commit.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(TypeSafeBadRequestError(400, {}, Headers()), id="bad-request"),
        pytest.param(TypeSafeUnprocessableEntityError(422, {}, Headers()), id="unprocessable"),
    ],
)
def test_rejected_batch_is_skipped_without_an_assessment(monkeypatch, error):
    writer = Mock(spec=Session)
    _sessions(monkeypatch=monkeypatch, reader=Mock(spec=Session), writer=writer)
    monkeypatch.setattr(
        module,
        "get_case",
        Mock(return_value=_case(target_speaker_id="A", target_revision=2)),
    )
    monkeypatch.setattr(module, "read_handled_through", Mock(return_value=0))
    monkeypatch.setattr(
        module,
        "load_case_speech",
        Mock(
            return_value=[
                _ingested(observation_id="one", sequence=1, speaker_id="A"),
                _ingested(observation_id="two", sequence=2, speaker_id="B"),
            ]
        ),
    )
    monkeypatch.setattr(module, "find_evidence", Mock(return_value=None))
    monkeypatch.setattr(module.jev, "evaluate", Mock(side_effect=error))
    store = Mock()
    monkeypatch.setattr(module, "store_assessment", store)
    mark_handled = Mock()
    monkeypatch.setattr(module, "mark_handled", mark_handled)

    assert module.process_case(**KWARGS) is None

    store.assert_not_called()
    mark_handled.assert_called_once_with(
        case_id="case", target_revision=2, through_sequence=1, session=writer
    )
    writer.commit.assert_called_once()
