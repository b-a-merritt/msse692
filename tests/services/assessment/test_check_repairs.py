import pytest
from sqlmodel import select

from normative_conformance.database import read_session
from normative_conformance.errors import StorageUnavailable
from normative_conformance.models.assessment import Assessment


def test_repair_can_resolve_multiple_pending_models(*, add_observation, assess, check):
    add_observation(start=0, end=0.9, transcript="you are a liar", level=-17.0)
    add_observation(start=1, end=32)
    pending = assess()
    assert len(pending) == 2
    add_observation(start=33, end=34, transcript="I am sorry", received=105)
    resolutions = [row for row in check(at=105) if row.resolves_assessment_id is not None]
    assert {row.resolves_assessment_id for row in resolutions} == {
        row.assessment_id for row in pending
    }
    assert all(row.status == "non-conformant" for row in resolutions)


def test_repair_searches_and_resolutions_share_one_subject_lookup(
    *, add_observation, assess, check, subject_config_reads
):
    add_observation(start=0, end=0.9, transcript="you are a liar", level=-17.0)
    add_observation(start=1, end=32)
    assess()
    add_observation(start=33, end=34, transcript="I apologize", received=105)
    subject_config_reads.clear()

    results = check(at=105)

    assert len(results) == 3
    assert len(subject_config_reads) == 1


def test_late_repair_resets_future_detection_without_retracting_positive(
    *,
    add_observation,
    assess,
    check,
    session,
):
    add_observation(start=0, end=0.9, transcript="you are a liar", level=-17.0)
    assess()
    final = check()[0]
    before = final.model_dump()
    add_observation(start=1, end=2, transcript="I apologize", received=111)
    check(at=111)
    add_observation(start=3, end=3.9, transcript="you are a liar", level=-17.0, received=112)
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
    add_observation(start=0, end=0.9, transcript="you are a liar", level=-17.0)
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
    add_observation(start=0, end=0.9, transcript="you are a liar", level=-17.0)
    assess()

    results = check(at=at)

    assert results[0].status == ("pending" if at < 110 else "conformant")
    assert scheduler.queued_cases == set()


def test_failed_resolution_rolls_back_repair_before_requesting_assessment(
    *, add_observation, assess, check, engine, scheduler
):
    add_observation(start=0, end=0.9, transcript="you are a liar", level=-17.0)
    original = assess()[0]
    add_observation(start=1, end=2, transcript="I apologize", received=105)
    # The apology is stored first; a failed resolution must roll it back too.
    with engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE TRIGGER fail_resolution BEFORE INSERT ON assessment
            WHEN NEW.resolves_assessment_id IS NOT NULL
            BEGIN SELECT RAISE(ABORT, 'Resolution write failed'); END
        """)

    with pytest.raises(StorageUnavailable, match="Repairs could not be checked"):
        check(at=105)

    with read_session(engine=engine) as session:
        rows = session.exec(select(Assessment)).all()
        assert [row.model_dump() for row in rows] == [original.model_dump()]
    assert scheduler.queued_cases == set()
