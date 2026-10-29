from datetime import UTC
from datetime import datetime
from unittest.mock import MagicMock
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from normative_conformance.errors import CaptureFailure
from normative_conformance.models.speaker_revision import ReplacedObservation
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.schemas.observation import ObservationReplacement
from normative_conformance.services.capture import store_revisions as module
from normative_conformance.services.observation.load_case_speech import IngestedObservation


def test_stores_each_replacement_as_a_revision_with_its_corrected_speech(monkeypatch):
    original = ObservationInput(
        case_id="case",
        observation_id="original-a",
        speaker_id="A",
        start_at="1970-01-01T00:00:01Z",
        end_at="1970-01-01T00:00:01.100000Z",
        transcript="Hello",
        signal_level_min=-50,
        signal_level_avg=-30,
        signal_level_max=-10,
    )
    observation = original.model_copy(update={"observation_id": "regrouped", "speaker_id": "B"})
    # Only "original-a" was ingested, so the unknown "original-b" is not recorded as replaced.
    replacement = ObservationReplacement(
        replaced_observation_ids=["original-a", "original-b"], observations=[observation]
    )
    monkeypatch.setattr(
        module,
        "load_case_speech",
        lambda **kwargs: [
            IngestedObservation(
                observation_key=3,
                sequence=1,
                received_at=datetime(1970, 1, 1, 0, 0, 2, tzinfo=UTC),
                observation=original,
            )
        ],
    )
    corrections = []
    monkeypatch.setattr(module, "stage_correction", lambda **kwargs: corrections.append(kwargs))
    revisions = []
    session = Mock(spec=Session)
    session.add.side_effect = revisions.append
    # The database assigns the revision ID when the revision is flushed.
    session.flush.side_effect = lambda: setattr(revisions[-1], "speaker_revision_id", 7)
    context = MagicMock()
    context.__enter__.return_value = session
    monkeypatch.setattr(module, "write_session", Mock(return_value=context))

    module.store_revisions(
        case_id="case",
        replacements=[replacement],
        engine=object(),
        now=lambda: datetime(1970, 1, 1, 0, 0, 5, tzinfo=UTC),
    )

    assert [row.model_dump() for row in revisions] == [
        {"speaker_revision_id": 7, "case_id": "case", "received_at_us": 5_000_000}
    ]
    assert session.add_all.call_args.args[0] == [
        ReplacedObservation(speaker_revision_id=7, observation_key=3)
    ]
    assert corrections == [
        {"observation": observation, "speaker_revision_id": 7, "session": session}
    ]
    session.commit.assert_called_once()


def test_empty_revision_batch_does_not_open_storage(monkeypatch):
    write = Mock(side_effect=AssertionError("Storage must not be opened"))
    monkeypatch.setattr(module, "write_session", write)
    module.store_revisions(
        case_id="case",
        replacements=[],
        engine=object(),
        now=lambda: datetime(1970, 1, 1, tzinfo=UTC),
    )
    write.assert_not_called()


@pytest.mark.parametrize(
    "owner,operation",
    [
        pytest.param("context", "__enter__", id="open"),
        pytest.param("session", "commit", id="commit"),
    ],
)
def test_storage_failures_are_capture_failures(monkeypatch, owner, operation):
    session = Mock(spec=Session)
    context = MagicMock()
    context.__enter__.return_value = session
    failure = SQLAlchemyError("private storage details")
    session.flush.side_effect = lambda: setattr(
        session.add.call_args.args[0], "speaker_revision_id", 7
    )
    getattr({"context": context, "session": session}[owner], operation).side_effect = failure
    monkeypatch.setattr(module, "write_session", Mock(return_value=context))
    monkeypatch.setattr(module, "load_case_speech", lambda **kwargs: [])
    monkeypatch.setattr(module, "stage_correction", Mock())
    observation = ObservationInput(
        case_id="case",
        observation_id="replacement",
        speaker_id="B",
        start_at="1970-01-01T00:00:00Z",
        end_at="1970-01-01T00:00:01Z",
        transcript="Hello",
        signal_level_min=-30,
        signal_level_avg=-30,
        signal_level_max=-30,
    )
    with pytest.raises(CaptureFailure) as caught:
        module.store_revisions(
            case_id="case",
            replacements=[
                ObservationReplacement(
                    replaced_observation_ids=["original"], observations=[observation]
                )
            ],
            engine=object(),
            now=lambda: datetime(1970, 1, 1, tzinfo=UTC),
        )
    assert caught.value.code == "storageUnavailable"
