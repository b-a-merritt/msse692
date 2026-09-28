"""Delivery marks pending interventions sent once, in the same transaction that reads them."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import OperationalError

from normative_conformance.database import write_session
from normative_conformance.errors import StorageUnavailable
from normative_conformance.services.intervention.deliver_pending import deliver_pending
from normative_conformance.services.intervention.list_intervention_records import (
    list_intervention_records,
)

from .conftest import at


@pytest.fixture
def deliver(*, engine):
    def deliver(*, now=110):
        with write_session(engine=engine) as session:
            return deliver_pending(session=session, now=lambda: at(now))

    return deliver


def test_nothing_pending_returns_an_empty_list(*, add_assessment, deliver):
    assert deliver() == []


def test_pending_interventions_are_returned_sent_once(*, session, add_assessment, create, deliver):
    add_assessment(model_id="harm_phrase")
    create()
    pending = list_intervention_records(session=session)[0]
    session.commit()

    delivered = deliver(now=110)
    assert delivered == [pending.model_copy(update={"status": "sent", "sent_at": at(110)})]
    assert list_intervention_records(session=session) == delivered
    assert deliver(now=111) == []


def test_sent_interventions_are_excluded(*, session, add_assessment, create, deliver):
    add_assessment(model_id="harm_phrase")
    create()
    deliver(now=110)
    add_assessment(model_id="extended_turn", at=111)
    create(since=111, now=112)
    second = list_intervention_records(status="pending", session=session)[0]
    session.commit()

    assert [record.intervention_id for record in deliver(now=113)] == [second.intervention_id]
    assert [record.sent_at for record in list_intervention_records(session=session)] == [
        at(110),
        at(113),
    ]


def test_failure_before_commit_leaves_interventions_pending(
    *, session, engine, add_assessment, create, monkeypatch
):
    add_assessment(model_id="harm_phrase")
    create()

    with write_session(engine=engine) as delivery_session:
        monkeypatch.setattr(
            delivery_session,
            "commit",
            Mock(side_effect=OperationalError("COMMIT", {}, Exception("disk I/O error"))),
        )
        with pytest.raises(StorageUnavailable, match="The interventions could not be delivered"):
            deliver_pending(session=delivery_session, now=lambda: at(110))

    assert [record.status for record in list_intervention_records(session=session)] == ["pending"]


def test_concurrent_delivery_returns_each_intervention_once(
    *, session, add_assessment, create, deliver
):
    add_assessment(model_id="harm_phrase")
    create()
    add_assessment(model_id="extended_turn", at=103)
    create(since=103, now=105)
    pending = list_intervention_records(session=session)
    session.commit()
    start = Barrier(2)

    def deliver_together():
        start.wait(timeout=5)
        return deliver(now=110)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(deliver_together) for _ in range(2)]
        batches = [future.result(timeout=10) for future in futures]

    assert sorted(len(batch) for batch in batches) == [0, 2]
    assert sorted(record.intervention_id for batch in batches for record in batch) == [
        record.intervention_id for record in pending
    ]
    assert all(record.sent_at == at(110) for batch in batches for record in batch)
