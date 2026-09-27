import pytest

from normative_conformance.models.assessment import Assessment
from normative_conformance.schemas.assessment import Explanation
from normative_conformance.services.assessment.list_assessments import list_assessments


@pytest.mark.parametrize(
    "received,expected", [(109.999999, "non-conformant"), (110, "conformant"), (111, "conformant")]
)
def test_repair_uses_fixed_deadline_when_check_is_delayed(
    *,
    add_observation,
    assess,
    resolve,
    session,
    received,
    expected,
):
    add_observation(start=0, end=0.9, transcript="stop that right now", level=-17.0)
    original = assess()[0]
    before = original.model_dump()
    add_observation(start=1, end=2, transcript="I apologize", received=received)
    resolution = resolve(pending=original, at=120)
    assert resolution.resolves_assessment_id == original.assessment_id
    assert resolution.status == expected
    explanation = Explanation.model_validate_json(resolution.explanation_json)
    repaired = expected == "non-conformant"
    assert explanation.reason_code == ("repaired" if repaired else "matched")
    assert explanation.rules[0].outcome == ("not_satisfied" if repaired else "satisfied")
    assert explanation.rules[0].observation_ids == (["2"] if repaired else [])
    assert session.get(Assessment, original.assessment_id).model_dump() == before
    assert list_assessments(status="pending", unresolved=True, session=session) == []


def test_older_speech_arriving_later_does_not_cancel_pending(*, add_observation, assess, resolve):
    add_observation(start=3, end=3.9, transcript="stop that right now", level=-17.0)
    pending = assess()[0]
    add_observation(start=0, end=1, transcript="I apologize", received=105)
    assert resolve(pending=pending).status == "conformant"


def test_latest_late_repair_does_not_hide_earlier_timely_repair(
    *, add_observation, assess, resolve
):
    add_observation(start=0, end=0.9, transcript="stop that right now", level=-17.0)
    pending = assess()[0]
    add_observation(start=1, end=2, transcript="I apologize", received=105)
    add_observation(start=3, end=4, transcript="I am sorry", received=115)
    assert resolve(pending=pending, at=120).status == "non-conformant"


def test_repair_checks_original_evidence_even_when_later_speech_matches(
    *, add_observation, assess, resolve
):
    add_observation(start=0, end=0.9, transcript="stop that right now", level=-17.0)
    pending = assess()[0]
    add_observation(start=3, end=3.9, transcript="stop it right now", level=-17.0, received=104)
    add_observation(start=1, end=2, transcript="I apologize", received=105)

    result = resolve(pending=pending, at=105)

    assert result.status == "non-conformant"
    assert result.resolves_assessment_id == pending.assessment_id
    assert pending.through_sequence == 1
    assert result.through_sequence == 3
