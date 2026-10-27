import pytest

from normative_conformance.models.case import ConversationCase
from normative_conformance.models.case import TargetAssignment
from normative_conformance.services.scheduler.run_worker.progress import read_handled_through


@pytest.mark.parametrize(
    "assigned_revisions,expected",
    [
        pytest.param([1], 4, id="same-target-continues"),
        pytest.param([1, 2], 0, id="changed-target-restarts"),
    ],
)
def test_handled_progress_applies_only_to_the_current_target(session, assigned_revisions, expected):
    session.add(
        ConversationCase(
            case_id="case",
            created_at_us=0,
            last_handled_sequence=4,
            last_handled_target_revision=1,
        )
    )
    session.flush()
    session.add_all(
        [
            TargetAssignment(
                case_id="case", target_revision=revision, assigned_at_us=0, speaker_id="A"
            )
            for revision in assigned_revisions
        ]
    )
    session.commit()

    assert read_handled_through(case_id="case", session=session) == expected
