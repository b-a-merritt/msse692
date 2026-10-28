from datetime import UTC
from datetime import datetime
from importlib import import_module
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from normative_conformance.errors import StorageUnavailable

module = import_module("normative_conformance.services.intervention.deliver_pending")


def test_returns_updated_records_only_after_commit(*, monkeypatch):
    session = Mock(spec=Session)
    session.exec.return_value.scalars.return_value = iter([2, 5])
    records = [object(), object()]
    listing = Mock(return_value=records)
    monkeypatch.setattr(module, "list_intervention_records", listing)

    def clock():
        return datetime(1970, 1, 1, 0, 0, 0, 100, tzinfo=UTC)

    result = module.deliver_pending(case_id="requested", session=session, now=clock)
    assert result == records
    listing.assert_called_once_with(intervention_ids=[2, 5], session=session, now=clock)
    session.commit.assert_called_once()


def test_nothing_pending_returns_nothing_without_committing(*, monkeypatch):
    session = Mock(spec=Session)
    session.exec.return_value.scalars.return_value = iter([])
    listing = Mock()
    monkeypatch.setattr(module, "list_intervention_records", listing)
    result = module.deliver_pending(
        case_id="requested",
        session=session,
        now=lambda: datetime(1970, 1, 1, 0, 0, 0, 100, tzinfo=UTC),
    )
    assert result == []
    listing.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.parametrize("stage", ["connection", "exec", "commit"])
def test_delivery_failure_rolls_back_and_returns_no_success(*, monkeypatch, stage):
    session = Mock(spec=Session)
    session.exec.return_value.scalars.return_value = [2]
    monkeypatch.setattr(module, "list_intervention_records", Mock(return_value=[object()]))
    error = SQLAlchemyError("Private driver details")
    getattr(session, stage).side_effect = error
    with pytest.raises(
        StorageUnavailable, match=r"^The interventions could not be delivered$"
    ) as caught:
        module.deliver_pending(
            case_id="requested",
            session=session,
            now=lambda: datetime(1970, 1, 1, tzinfo=UTC),
        )
    session.rollback.assert_called_once()
    assert caught.value.__cause__ is error
