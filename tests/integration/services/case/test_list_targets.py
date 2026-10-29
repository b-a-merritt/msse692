"""Each of a case's target revisions maps to its speaker label."""

from normative_conformance.models.case import ConversationCase
from normative_conformance.models.case import TargetAssignment
from normative_conformance.services.case.list_targets import list_targets


def test_maps_each_revision_of_the_case_to_its_label(session):
    session.add_all(
        [
            ConversationCase(case_id="case", created_at_us=0),
            ConversationCase(case_id="other", created_at_us=0),
        ]
    )
    session.flush()
    session.add_all(
        [
            TargetAssignment(case_id="case", target_revision=1, assigned_at_us=0, speaker_id="A"),
            TargetAssignment(case_id="case", target_revision=2, assigned_at_us=1),
            TargetAssignment(case_id="other", target_revision=1, assigned_at_us=0, speaker_id="B"),
        ]
    )
    session.commit()

    assert list_targets(case_id="case", session=session) == {1: "A", 2: None}
