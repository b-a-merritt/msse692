import pytest
from sqlmodel import col
from sqlmodel import select

from normative_conformance import models
from normative_conformance.services.intervention.is_pending import is_pending


def _assessment(*, target_revision, after_sequence, through_sequence, action):
    return models.Assessment(
        case_id="case",
        target_revision=target_revision,
        model_id="jev-1.14.0",
        prompt_version="conversation-1",
        evaluated_at_us=0,
        completed_at_us=0,
        after_sequence=after_sequence,
        through_sequence=through_sequence,
        action=action,
        action_confidence=None if action is None else 0.9,
        selection_threshold=0.7,
        request_json="{}",
    )


@pytest.mark.parametrize(
    "now_us,assignments,later_actions,sent_at_us,expected",
    [
        pytest.param(60_000_000, [(1, "A")], [], None, ["Feedback"], id="fresh"),
        pytest.param(70_000_000, [(1, "A")], [], None, [], id="older-than-a-minute"),
        pytest.param(60_000_000, [(1, "A")], [], 20_000_000, [], id="sent"),
        pytest.param(60_000_000, [(1, "A"), (2, "B")], [], None, [], id="target-changed"),
        pytest.param(
            60_000_000, [(1, "A")], ["remain_silent"], None, [], id="target-assessed-again"
        ),
        pytest.param(
            60_000_000, [(1, "A")], [None], None, ["Feedback"], id="only-other-speech-since"
        ),
    ],
)
def test_pending_interventions_still_describe_the_conversation(
    *, session, now_us, assignments, later_actions, sent_at_us, expected
):
    session.add(models.ConversationCase(case_id="case", created_at_us=0))
    session.flush()
    session.add_all(
        [
            models.Observation(
                case_id="case",
                observation_id=str(sequence),
                sequence=sequence,
                received_at_us=0,
                start_at_us=0,
                end_at_us=1,
                speaker_id="A",
                transcript="hello",
                signal_level_min=-40,
                signal_level_avg=-30,
                signal_level_max=-20,
            )
            for sequence in (1, 2)
        ]
        + [
            models.TargetAssignment(
                case_id="case", target_revision=revision, assigned_at_us=0, speaker_id=speaker
            )
            for revision, speaker in assignments
        ]
    )
    session.flush()
    source = _assessment(
        target_revision=1, after_sequence=0, through_sequence=1, action="intervene"
    )
    session.add(source)
    # A later batch for the same target; its action is null when it has no target speech.
    session.add_all(
        [
            _assessment(target_revision=1, after_sequence=1, through_sequence=2, action=action)
            for action in later_actions
        ]
    )
    session.flush()
    session.add(
        models.Intervention(
            assessment_id=source.assessment_id,
            message="Feedback",
            created_at_us=10_000_000,
            sent_at_us=sent_at_us,
        )
    )
    session.commit()

    assert (
        session.exec(
            select(col(models.Intervention.message)).where(is_pending(now_us=now_us))
        ).all()
        == expected
    )
