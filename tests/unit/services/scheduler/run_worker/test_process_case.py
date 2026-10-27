from contextlib import contextmanager
from datetime import datetime
from datetime import timezone
from importlib import import_module
from unittest.mock import Mock

import pytest
from sqlmodel import Session

from normative_conformance.models.assessment import Assessment
from normative_conformance.models.case import CaseLog
from normative_conformance.models.case import TargetAssignment
from normative_conformance.schemas.decision import DecisionAnswers
from normative_conformance.schemas.observation import ObservationRecord
from normative_conformance.schemas.observation import ObservationReplacement
from normative_conformance.services.observation.load_case_speech import CaseSpeech

module = import_module("normative_conformance.services.scheduler.run_worker.process_case")


def _record(*, observation_id, sequence):
    return ObservationRecord(
        case_id="case",
        observation_id=observation_id,
        speaker_id="A",
        start_at=datetime.fromtimestamp(sequence, timezone.utc),
        end_at=datetime.fromtimestamp(sequence + 0.5, timezone.utc),
        transcript="Hello",
        signal_level_min=-40,
        signal_level_avg=-30,
        signal_level_max=-20,
        received_at=datetime.fromtimestamp(sequence, timezone.utc),
        updated_at=datetime.fromtimestamp(sequence, timezone.utc),
        sequence=sequence,
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


RESULT = DecisionAnswers(
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
    "case,assignment,last_handled_sequence,sequences",
    [
        pytest.param(None, None, 0, [1], id="missing-case"),
        pytest.param(CaseLog(case_id="case", created_at_us=0), None, 0, [1], id="no-target"),
        pytest.param(
            CaseLog(case_id="case", created_at_us=0),
            TargetAssignment(case_id="case", target_revision=1, assigned_at_us=0),
            0,
            [1],
            id="unresolved-target",
        ),
        pytest.param(
            CaseLog(case_id="case", created_at_us=0),
            TargetAssignment(case_id="case", target_revision=1, assigned_at_us=0, speaker_id="A"),
            0,
            [],
            id="no-speech",
        ),
        pytest.param(
            CaseLog(
                case_id="case",
                created_at_us=0,
                last_handled_sequence=2,
                last_handled_target_revision=1,
            ),
            TargetAssignment(case_id="case", target_revision=1, assigned_at_us=0, speaker_id="A"),
            2,
            [1, 2],
            id="handled",
        ),
    ],
)
def test_cases_without_new_speech_for_a_resolved_target_are_skipped(
    monkeypatch, case, assignment, last_handled_sequence, sequences
):
    reader, writer = Mock(spec=Session), Mock(spec=Session)
    reader.get.return_value = case
    _sessions(monkeypatch=monkeypatch, reader=reader, writer=writer)
    monkeypatch.setattr(module, "current_assignment", Mock(return_value=assignment))
    monkeypatch.setattr(
        module,
        "load_case_speech",
        Mock(
            return_value=CaseSpeech(
                observations=[
                    _record(observation_id=str(sequence), sequence=sequence)
                    for sequence in sequences
                ],
                revisions=[],
                observation_keys={},
            )
        ),
    )
    evaluate = Mock()
    monkeypatch.setattr(module.jev, "evaluate", evaluate)

    assert module.process_case(**KWARGS) is None

    evaluate.assert_not_called()
    writer.commit.assert_not_called()


@pytest.mark.parametrize(
    "handled_revision,after_sequence,through_sequence",
    [
        pytest.param(2, 1, 2, id="same-target-continues"),
        pytest.param(1, 0, 1, id="changed-target-restarts"),
    ],
)
def test_snapshot_is_taken_outside_transactions_and_progress_commits_with_the_result(
    monkeypatch, handled_revision, after_sequence, through_sequence
):
    case = CaseLog(
        case_id="case",
        created_at_us=0,
        last_handled_sequence=1,
        last_handled_target_revision=handled_revision,
    )
    current = case.model_copy()
    reader, writer = Mock(spec=Session), Mock(spec=Session)
    reader.get.return_value = case
    writer.get.return_value = current
    open_transactions = _sessions(monkeypatch=monkeypatch, reader=reader, writer=writer)
    assignment = TargetAssignment(
        case_id="case", target_revision=2, assigned_at_us=0, speaker_id="A"
    )
    monkeypatch.setattr(module, "current_assignment", Mock(return_value=assignment))
    speech = CaseSpeech(
        observations=[
            _record(observation_id="one", sequence=1),
            _record(observation_id="two", sequence=2),
        ],
        revisions=[],
        observation_keys={"one": 10, "two": 20},
    )
    monkeypatch.setattr(module, "load_case_speech", Mock(return_value=speech))
    snapshots = []

    def evaluate(*, snapshot, client):
        assert open_transactions == set()
        snapshots.append(snapshot)
        return RESULT, '{"state":{}}'

    monkeypatch.setattr(module.jev, "evaluate", evaluate)
    saved = Assessment(assessment_id=9)
    store = Mock(return_value=saved)
    monkeypatch.setattr(module, "store_assessment", store)

    assert module.process_case(**KWARGS) is saved

    [snapshot] = snapshots
    assert (snapshot.target_speaker_id, snapshot.target_revision) == ("A", 2)
    assert (snapshot.after_sequence, snapshot.through_sequence) == (
        after_sequence,
        through_sequence,
    )
    assert store.call_args.kwargs["snapshot"] is snapshot
    assert store.call_args.kwargs["observation_keys"] == {"one": 10, "two": 20}
    assert (current.last_handled_sequence, current.last_handled_target_revision) == (
        through_sequence,
        2,
    )
    writer.commit.assert_called_once()


def test_target_change_during_the_call_keeps_the_decision_but_not_the_progress(monkeypatch):
    case = CaseLog(
        case_id="case", created_at_us=0, last_handled_sequence=1, last_handled_target_revision=2
    )
    current = case.model_copy()
    reader, writer = Mock(spec=Session), Mock(spec=Session)
    reader.get.return_value = case
    writer.get.return_value = current
    _sessions(monkeypatch=monkeypatch, reader=reader, writer=writer)
    monkeypatch.setattr(
        module,
        "current_assignment",
        Mock(
            side_effect=[
                TargetAssignment(
                    case_id="case", target_revision=2, assigned_at_us=0, speaker_id="A"
                ),
                TargetAssignment(
                    case_id="case", target_revision=3, assigned_at_us=1, speaker_id="B"
                ),
            ]
        ),
    )
    monkeypatch.setattr(
        module,
        "load_case_speech",
        Mock(
            return_value=CaseSpeech(
                observations=[
                    _record(observation_id="one", sequence=1),
                    _record(observation_id="two", sequence=2),
                ],
                revisions=[],
                observation_keys={"one": 10, "two": 20},
            )
        ),
    )
    monkeypatch.setattr(module.jev, "evaluate", Mock(return_value=(RESULT, "{}")))
    store = Mock(return_value=Assessment(assessment_id=9))
    monkeypatch.setattr(module, "store_assessment", store)

    module.process_case(**KWARGS)

    store.assert_called_once()
    assert (current.last_handled_sequence, current.last_handled_target_revision) == (1, 2)
    writer.commit.assert_called_once()


@pytest.mark.parametrize(
    "provider_error,storage_error",
    [
        pytest.param(RuntimeError("Unavailable"), None, id="provider"),
        pytest.param(None, RuntimeError("Disk failed"), id="storage"),
    ],
)
def test_failures_leave_progress_unchanged(monkeypatch, provider_error, storage_error):
    case = CaseLog(
        case_id="case", created_at_us=0, last_handled_sequence=1, last_handled_target_revision=2
    )
    current = case.model_copy()
    reader, writer = Mock(spec=Session), Mock(spec=Session)
    reader.get.return_value = case
    writer.get.return_value = current
    _sessions(monkeypatch=monkeypatch, reader=reader, writer=writer)
    monkeypatch.setattr(
        module,
        "current_assignment",
        Mock(
            return_value=TargetAssignment(
                case_id="case", target_revision=2, assigned_at_us=0, speaker_id="A"
            )
        ),
    )
    monkeypatch.setattr(
        module,
        "load_case_speech",
        Mock(
            return_value=CaseSpeech(
                observations=[
                    _record(observation_id="one", sequence=1),
                    _record(observation_id="two", sequence=2),
                ],
                revisions=[],
                observation_keys={"one": 10, "two": 20},
            )
        ),
    )
    monkeypatch.setattr(
        module.jev, "evaluate", Mock(return_value=(RESULT, "{}"), side_effect=provider_error)
    )
    monkeypatch.setattr(module, "store_assessment", Mock(side_effect=storage_error))

    with pytest.raises(RuntimeError) as caught:
        module.process_case(**KWARGS)

    assert caught.value is (provider_error or storage_error)
    assert current.last_handled_sequence == 1
    writer.commit.assert_not_called()


def test_batch_whose_speech_was_removed_is_handled_without_assessment(monkeypatch):
    case = CaseLog(
        case_id="case", created_at_us=0, last_handled_sequence=1, last_handled_target_revision=2
    )
    current = case.model_copy()
    reader, writer = Mock(spec=Session), Mock(spec=Session)
    reader.get.return_value = case
    writer.get.return_value = current
    _sessions(monkeypatch=monkeypatch, reader=reader, writer=writer)
    monkeypatch.setattr(
        module,
        "current_assignment",
        Mock(
            return_value=TargetAssignment(
                case_id="case", target_revision=2, assigned_at_us=0, speaker_id="A"
            )
        ),
    )
    monkeypatch.setattr(
        module,
        "load_case_speech",
        Mock(
            return_value=CaseSpeech(
                observations=[
                    _record(observation_id="one", sequence=1),
                    _record(observation_id="two", sequence=2),
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

    assert module.process_case(**KWARGS) is None

    evaluate.assert_not_called()
    store.assert_not_called()
    assert (current.last_handled_sequence, current.last_handled_target_revision) == (2, 2)
    writer.commit.assert_called_once()
