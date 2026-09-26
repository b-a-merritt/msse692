import pytest
from sqlmodel import select

from normative_conformance.database import read_session
from normative_conformance.models.assessment import Assessment
from normative_conformance.services.assessment.list_pending import list_pending


@pytest.mark.parametrize(
    "received,expected", [(109.999999, "non-conformant"), (110, "conformant"), (111, "conformant")]
)
def test_repair_uses_fixed_deadline_when_check_is_delayed(
    *,
    add_observation,
    assess,
    check,
    session,
    received,
    expected,
):
    add_observation(start=0, end=0.9, transcript="you are wrong", level=-17.0)
    original = assess()[0]
    before = original.model_dump()
    add_observation(start=1, end=2, transcript="I apologize", received=received)
    results = check(at=120)
    resolution = next(row for row in results if row.resolves_assessment_id is not None)
    assert resolution.resolves_assessment_id == original.assessment_id
    assert resolution.status == expected
    assert session.get(Assessment, original.assessment_id).model_dump() == before
    assert list_pending(session=session) == []
    session.commit()
    assert check(at=121) == []


def test_repair_can_resolve_multiple_pending_models(*, add_observation, assess, check):
    add_observation(start=0, end=0.9, transcript="you are wrong", level=-17.0)
    add_observation(start=1, end=32)
    pending = assess()
    assert len(pending) == 2
    add_observation(start=33, end=34, transcript="I am sorry", received=105)
    resolutions = [row for row in check(at=105) if row.resolves_assessment_id is not None]
    assert {row.resolves_assessment_id for row in resolutions} == {
        row.assessment_id for row in pending
    }
    assert all(row.status == "non-conformant" for row in resolutions)


def test_older_speech_arriving_later_does_not_cancel_pending(*, add_observation, assess, check):
    add_observation(start=3, end=3.9, transcript="you are wrong", level=-17.0)
    assess()
    add_observation(start=0, end=1, transcript="I apologize", received=105)
    results = check()
    assert (
        next(row for row in results if row.resolves_assessment_id is not None).status
        == "conformant"
    )


def test_latest_late_repair_does_not_hide_earlier_timely_repair(*, add_observation, assess, check):
    add_observation(start=0, end=0.9, transcript="you are wrong", level=-17.0)
    assess()
    add_observation(start=1, end=2, transcript="I apologize", received=105)
    add_observation(start=3, end=4, transcript="I am sorry", received=115)
    results = check(at=120)
    assert (
        next(row for row in results if row.resolves_assessment_id is not None).status
        == "non-conformant"
    )


def test_late_repair_resets_future_detection_without_retracting_positive(
    *,
    add_observation,
    assess,
    check,
    session,
):
    add_observation(start=0, end=0.9, transcript="you are wrong", level=-17.0)
    assess()
    final = check()[0]
    before = final.model_dump()
    add_observation(start=1, end=2, transcript="I apologize", received=111)
    check(at=111)
    add_observation(start=3, end=3.9, transcript="you are wrong", level=-17.0, received=112)
    new = assess(at=112)[0]
    assert new.status == "pending"
    assert new.next_due_at_us == 122_000_000
    assert session.get(Assessment, final.assessment_id).model_dump() == before


def test_repair_resets_incomplete_interruption_pattern(*, add_observation, assess, check):
    add_observation(start=0, end=20, speaker="other")
    add_observation(start=1, end=2)
    add_observation(start=3, end=4)
    add_observation(start=5, end=6, transcript="I apologize")
    add_observation(start=7, end=8)
    # Detection submits a candidate; the separate repair check removes the old evidence.
    assess()
    check(at=100)
    assert assess(at=101) == []


def test_repeated_checks_append_only_one_resolution(*, add_observation, assess, check, session):
    add_observation(start=0, end=31)
    assess()
    first = check()
    assert len(first) == 1
    assert check(at=111) == []
    assert len(session.exec(select(Assessment)).all()) == 2


@pytest.mark.parametrize("stopping", [False, True])
def test_repair_requests_assessment_after_commit_unless_stopping(
    *, add_observation, assess, check, engine, scheduler, assessment_queue, monkeypatch, stopping
):
    add_observation(start=0, end=0.9, transcript="you are wrong", level=-17.0)
    original = assess()[0]
    add_observation(start=1, end=2, transcript="I apologize", received=105)
    put = assessment_queue.put
    requested = []

    def enqueue(*, item):
        with read_session(engine=engine) as session:
            resolution = session.exec(
                select(Assessment).where(
                    Assessment.resolves_assessment_id == original.assessment_id
                )
            ).one()
            assert resolution.status == "non-conformant"
        requested.append(item["kind"])
        return put(item=item)

    monkeypatch.setattr(assessment_queue, "put", enqueue)
    if stopping:
        scheduler.stopped.set()
    results = check(at=105)

    assert any(row.resolves_assessment_id == original.assessment_id for row in results)
    assert requested == ([] if stopping else ["assess_case"])


@pytest.mark.parametrize("at", [105, 110])
def test_check_without_repair_does_not_request_assessment(
    *, add_observation, assess, check, scheduler, at
):
    add_observation(start=0, end=0.9, transcript="you are wrong", level=-17.0)
    assess()

    results = check(at=at)

    assert results[0].status == ("pending" if at < 110 else "conformant")
    assert scheduler.queued_cases == set()
