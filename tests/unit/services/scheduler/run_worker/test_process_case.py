from contextlib import contextmanager
from datetime import datetime
from datetime import timezone
from importlib import import_module
from unittest.mock import Mock

import pytest
from sqlmodel import Session

from normative_conformance.models.assessment import Assessment
from normative_conformance.models.case import TargetAssignment
from normative_conformance.schemas.decision import DecisionAnswers
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.schemas.observation import ObservationReplacement
from normative_conformance.services.observation.load_case_speech import CaseSpeech
from normative_conformance.services.observation.load_case_speech import IngestedObservation

module = import_module("normative_conformance.services.scheduler.run_worker.process_case")


def _ingested(*, observation_id, sequence):
    return IngestedObservation(
        sequence=sequence,
        observation=ObservationInput(
            case_id="case",
            observation_id=observation_id,
            speaker_id="A",
            start_at=datetime.fromtimestamp(sequence, timezone.utc),
            end_at=datetime.fromtimestamp(sequence + 0.5, timezone.utc),
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
    "batch_size": 1,
    "context_seconds": 30,
    "now": lambda: datetime(1970, 1, 1, tzinfo=timezone.utc),
}


@pytest.mark.parametrize(
    "assignment,handled_through,sequences",
    [
        pytest.param(None, 0, [1], id="no-target"),
        pytest.param(
            TargetAssignment(case_id="case", target_revision=1, assigned_at_us=0),
            0,
            [1],
            id="unresolved-target",
        ),
        pytest.param(
            TargetAssignment(case_id="case", target_revision=1, assigned_at_us=0, speaker_id="A"),
            0,
            [],
            id="no-speech",
        ),
        pytest.param(
            TargetAssignment(case_id="case", target_revision=1, assigned_at_us=0, speaker_id="A"),
            2,
            [1, 2],
            id="handled",
        ),
    ],
)
def test_cases_without_new_speech_for_a_resolved_target_are_skipped(
    monkeypatch, assignment, handled_through, sequences
):
    writer = Mock(spec=Session)
    _sessions(monkeypatch=monkeypatch, reader=Mock(spec=Session), writer=writer)
    monkeypatch.setattr(module, "current_assignment", Mock(return_value=assignment))
    monkeypatch.setattr(module, "read_handled_through", Mock(return_value=handled_through))
    monkeypatch.setattr(
        module,
        "load_case_speech",
        Mock(
            return_value=CaseSpeech(
                ingested=[
                    _ingested(observation_id=str(sequence), sequence=sequence)
                    for sequence in sequences
                ],
                revisions=[],
                observation_keys={},
            )
        ),
    )
    evaluate = Mock()
    monkeypatch.setattr(module.jev, "evaluate", evaluate)
    mark_handled = Mock()
    monkeypatch.setattr(module, "mark_handled", mark_handled)

    assert module.process_case(**KWARGS) is None

    evaluate.assert_not_called()
    mark_handled.assert_not_called()
    writer.commit.assert_not_called()


def test_snapshot_is_taken_outside_transactions_and_progress_commits_with_the_result(
    monkeypatch,
):
    writer = Mock(spec=Session)
    open_transactions = _sessions(monkeypatch=monkeypatch, reader=Mock(spec=Session), writer=writer)
    monkeypatch.setattr(
        module,
        "current_assignment",
        Mock(
            return_value=TargetAssignment(
                case_id="case", target_revision=2, assigned_at_us=0, speaker_id="A"
            )
        ),
    )
    monkeypatch.setattr(module, "read_handled_through", Mock(return_value=1))
    monkeypatch.setattr(
        module,
        "load_case_speech",
        Mock(
            return_value=CaseSpeech(
                ingested=[
                    _ingested(observation_id="one", sequence=1),
                    _ingested(observation_id="two", sequence=2),
                    _ingested(observation_id="three", sequence=3),
                ],
                revisions=[],
                observation_keys={"one": 10, "two": 20, "three": 30},
            )
        ),
    )
    snapshots = []

    def evaluate(*, snapshot, client):
        assert open_transactions == set()
        snapshots.append(snapshot)
        return ANSWERS, '{"state":{}}'

    monkeypatch.setattr(module.jev, "evaluate", evaluate)
    saved = Assessment(assessment_id=9)
    store = Mock(return_value=saved)
    monkeypatch.setattr(module, "store_assessment", store)
    mark_handled = Mock()
    monkeypatch.setattr(module, "mark_handled", mark_handled)

    assert module.process_case(**KWARGS) is saved

    [snapshot] = snapshots
    assert (snapshot.target_speaker_id, snapshot.target_revision) == ("A", 2)
    assert (snapshot.after_sequence, snapshot.through_sequence) == (1, 2)
    assert store.call_args.kwargs["snapshot"] is snapshot
    assert store.call_args.kwargs["answers"] is ANSWERS
    assert store.call_args.kwargs["observation_keys"] == {"one": 10, "two": 20, "three": 30}
    mark_handled.assert_called_once_with(snapshot=snapshot, session=writer)
    writer.commit.assert_called_once()


@pytest.mark.parametrize(
    "provider_error,storage_error",
    [
        pytest.param(RuntimeError("Unavailable"), None, id="provider"),
        pytest.param(None, RuntimeError("Disk failed"), id="storage"),
    ],
)
def test_failures_leave_progress_unchanged(monkeypatch, provider_error, storage_error):
    writer = Mock(spec=Session)
    _sessions(monkeypatch=monkeypatch, reader=Mock(spec=Session), writer=writer)
    monkeypatch.setattr(
        module,
        "current_assignment",
        Mock(
            return_value=TargetAssignment(
                case_id="case", target_revision=2, assigned_at_us=0, speaker_id="A"
            )
        ),
    )
    monkeypatch.setattr(module, "read_handled_through", Mock(return_value=0))
    monkeypatch.setattr(
        module,
        "load_case_speech",
        Mock(
            return_value=CaseSpeech(
                ingested=[_ingested(observation_id="one", sequence=1)],
                revisions=[],
                observation_keys={"one": 10},
            )
        ),
    )
    monkeypatch.setattr(
        module.jev, "evaluate", Mock(return_value=(ANSWERS, "{}"), side_effect=provider_error)
    )
    monkeypatch.setattr(module, "store_assessment", Mock(side_effect=storage_error))
    mark_handled = Mock()
    monkeypatch.setattr(module, "mark_handled", mark_handled)

    with pytest.raises(RuntimeError) as caught:
        module.process_case(**KWARGS)

    assert caught.value is (provider_error or storage_error)
    mark_handled.assert_not_called()
    writer.commit.assert_not_called()


def test_batch_whose_speech_was_removed_is_handled_without_assessment(monkeypatch):
    writer = Mock(spec=Session)
    _sessions(monkeypatch=monkeypatch, reader=Mock(spec=Session), writer=writer)
    monkeypatch.setattr(
        module,
        "current_assignment",
        Mock(
            return_value=TargetAssignment(
                case_id="case", target_revision=2, assigned_at_us=0, speaker_id="A"
            )
        ),
    )
    monkeypatch.setattr(module, "read_handled_through", Mock(return_value=1))
    monkeypatch.setattr(
        module,
        "load_case_speech",
        Mock(
            return_value=CaseSpeech(
                ingested=[
                    _ingested(observation_id="one", sequence=1),
                    _ingested(observation_id="two", sequence=2),
                ],
                revisions=[
                    ObservationReplacement(replaced_observation_ids=["two"], observations=[])
                ],
                observation_keys={"one": 10, "two": 20},
            )
        ),
    )
    evaluate = Mock()
    monkeypatch.setattr(module.jev, "evaluate", evaluate)
    store = Mock()
    monkeypatch.setattr(module, "store_assessment", store)
    mark_handled = Mock()
    monkeypatch.setattr(module, "mark_handled", mark_handled)

    assert module.process_case(**KWARGS) is None

    evaluate.assert_not_called()
    store.assert_not_called()
    [call] = mark_handled.call_args_list
    assert call.kwargs["snapshot"].through_sequence == 2
    assert call.kwargs["session"] is writer
    writer.commit.assert_called_once()
