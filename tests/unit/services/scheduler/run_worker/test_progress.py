from unittest.mock import Mock

import pytest
from sqlmodel import Session

from normative_conformance.models.case import ConversationCase
from normative_conformance.models.case import TargetAssignment
from normative_conformance.schemas.decision import DecisionSnapshot
from normative_conformance.services.scheduler.run_worker import progress


@pytest.mark.parametrize(
    "current_revision,expected",
    [
        pytest.param(2, (4, 2), id="same-target-advances"),
        pytest.param(3, (1, 1), id="changed-target-stays-pending"),
    ],
)
def test_progress_advances_only_for_the_target_the_batch_was_assessed_for(
    monkeypatch, current_revision, expected
):
    conversation = ConversationCase(
        case_id="case", created_at_us=0, last_handled_sequence=1, last_handled_target_revision=1
    )
    session = Mock(spec=Session)
    session.get.return_value = conversation
    monkeypatch.setattr(
        progress,
        "current_assignment",
        Mock(
            return_value=TargetAssignment(
                case_id="case",
                target_revision=current_revision,
                assigned_at_us=0,
                speaker_id="A",
            )
        ),
    )
    snapshot = DecisionSnapshot(
        case_id="case",
        target_speaker_id="A",
        target_revision=2,
        after_sequence=1,
        through_sequence=4,
        captured_at="1970-01-01T00:00:00Z",
        observations=[],
        new_observation_ids=[],
    )

    progress.mark_handled(snapshot=snapshot, session=session)

    assert (
        conversation.last_handled_sequence,
        conversation.last_handled_target_revision,
    ) == expected
