import pytest
from sqlmodel import select

from normative_conformance.models.assessment import Assessment
from normative_conformance.models.case import CaseLog
from normative_conformance.models.normative_model import NormativeModelVersion
from normative_conformance.models.observation import Observation


def test_finalized_match_is_not_repeated_before_repair(
    *, add_observation, assess, assess_one, check, session
):
    add_observation(start=0, end=0.9, transcript="you are a liar", level=-17.0)
    original = assess()[0]
    final = check()[0]
    assert final.resolves_assessment_id == original.assessment_id
    add_observation(start=2, end=2.9, transcript="you are a liar", level=-17.0, received=111)
    assert assess_one(at=111).assessment_id == final.assessment_id
    assert len(session.exec(select(Assessment)).all()) == 2


def test_reuse_checks_original_evidence_when_resolution_includes_later_speech(
    *, add_observation, assess, assess_one, check
):
    add_observation(start=0, end=0.9, transcript="you are a liar", level=-17.0)
    original = assess()[0]
    add_observation(start=3, end=3.9, transcript="you are a fool", level=-17.0, received=109)
    final = check(at=110)[0]
    assert final.resolves_assessment_id == original.assessment_id
    assert original.through_sequence == 1
    assert final.through_sequence == 2

    # This late repair clears the original evidence, while the later speech still matches.
    add_observation(start=1, end=2, transcript="I apologize", received=111)
    check(at=111)
    new = assess_one(at=112)

    assert new.assessment_id != final.assessment_id
    assert new.status == "pending"
    assert new.next_due_at_us == 122_000_000


@pytest.mark.parametrize("repairable", [False, True])
def test_reuse_is_specific_to_model_and_version(
    *, add_observation, assess, assess_one, session, repairable
):
    add_observation(start=0, end=1)
    identities = [("always", "1"), ("always", "2"), ("other", "1")]
    for model_id, version in identities:
        session.add(
            NormativeModelVersion(
                model_id=model_id,
                version=version,
                name=model_id,
                type="undesired",
                repairable=repairable,
                rules_json='[{"rule_id":"always","description":"Always matches","sql":"SELECT 1"}]',
                parameters_json="{}",
            )
        )
    session.commit()
    originals = {(row.model_id, row.model_version): row for row in assess()}

    for model_id, version in identities:
        reused = assess_one(model_id=model_id, version=version, at=105)
        assert reused.model_dump() == originals[model_id, version].model_dump()

    assert len(session.exec(select(Assessment)).all()) == 3


def test_unresolved_pending_takes_precedence_over_a_later_result(
    *, add_observation, assess, assess_one, session
):
    add_observation(start=0, end=0.9, transcript="you are a liar", level=-17.0)
    pending = assess()[0]
    later = Assessment(
        **(
            pending.model_dump()
            | {
                "assessment_id": None,
                "evaluation_id": "later",
                "status": "conformant",
                "next_due_at_us": None,
            }
        )
    )
    session.add(later)
    session.commit()

    assert assess_one(at=105).assessment_id == pending.assessment_id


def test_reuse_is_specific_to_the_case(*, add_observation, assess, assess_one, session):
    observation = add_observation(start=0, end=0.9, transcript="you are a liar", level=-17.0)
    original = assess()[0]
    session.add(CaseLog(case_id="other", created_at_us=0))
    session.flush()
    session.add(Observation(**(observation.model_dump() | {"case_id": "other"})))
    session.flush()
    session.add(
        Assessment(
            **(
                original.model_dump()
                | {"assessment_id": None, "evaluation_id": "other", "case_id": "other"}
            )
        )
    )
    session.commit()

    assert assess_one(at=105).assessment_id == original.assessment_id
