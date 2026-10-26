import json
from datetime import datetime
from datetime import timezone
from unittest.mock import MagicMock
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from normative_conformance.errors import CaptureFailure
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.schemas.observation import ObservationReplacement
from normative_conformance.services.capture import store_revisions as module


def test_stores_replacement_ids_and_complete_observation_data(monkeypatch):
    observation = ObservationInput(
        case_id="case",
        observation_id="regrouped",
        speaker_id="B",
        start_at="1970-01-01T00:00:01Z",
        end_at="1970-01-01T00:00:01.100000Z",
        transcript="Hello",
        signal_level_min=-50,
        signal_level_avg=-30,
        signal_level_max=-10,
    )
    replacement = ObservationReplacement(
        replaced_observation_ids=["original-a", "original-b"], observations=[observation]
    )
    session = Mock(spec=Session)
    context = MagicMock()
    context.__enter__.return_value = session
    monkeypatch.setattr(module, "write_session", Mock(return_value=context))

    module.store_revisions(
        case_id="case",
        replacements=[replacement],
        engine=object(),
        now=lambda: datetime(1970, 1, 1, 0, 0, 5, tzinfo=timezone.utc),
    )

    row = session.add.call_args.args[0]
    assert row.case_id == "case"
    assert row.received_at_us == 5_000_000
    assert json.loads(row.replaced_observation_ids_json) == ["original-a", "original-b"]
    assert json.loads(row.observations_json) == [observation.model_dump(mode="json")]
    session.commit.assert_called_once()


def test_empty_revision_batch_does_not_open_storage(monkeypatch):
    write = Mock(side_effect=AssertionError("Storage must not be opened"))
    monkeypatch.setattr(module, "write_session", write)
    module.store_revisions(
        case_id="case",
        replacements=[],
        engine=object(),
        now=lambda: datetime(1970, 1, 1, tzinfo=timezone.utc),
    )
    write.assert_not_called()


@pytest.mark.parametrize("failure_at", ["open", "commit"])
def test_storage_failures_are_capture_failures(monkeypatch, failure_at):
    session = Mock(spec=Session)
    context = MagicMock()
    context.__enter__.return_value = session
    failure = SQLAlchemyError("private storage details")
    if failure_at == "open":
        context.__enter__.side_effect = failure
    else:
        session.commit.side_effect = failure
    monkeypatch.setattr(module, "write_session", Mock(return_value=context))
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
            now=lambda: datetime(1970, 1, 1, tzinfo=timezone.utc),
        )
    assert caught.value.code == "storageUnavailable"
