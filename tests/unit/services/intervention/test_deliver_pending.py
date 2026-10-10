from datetime import datetime
from datetime import timezone
from importlib import import_module
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from normative_conformance.errors import StorageUnavailable

module = import_module("normative_conformance.services.intervention.deliver_pending")


@pytest.mark.parametrize("ids", [[], [2, 5]])
def test_returns_updated_records_only_after_commit(*, monkeypatch, ids):
    session = Mock(spec=Session)
    session.exec.return_value.scalars.return_value = iter(ids)
    records = [object() for _ in ids]
    listing = Mock(return_value=records)
    monkeypatch.setattr(module, "list_intervention_records", listing)
    result = module.deliver_pending(
        session=session, now=lambda: datetime(1970, 1, 1, 0, 0, 0, 100, tzinfo=timezone.utc)
    )
    assert result == records
    query = session.exec.call_args.args[0].compile()
    assert query.params["sent_at_us"] == 100
    assert "sent_at_us IS NULL" in str(query)
    assert "RETURNING intervention.intervention_id" in str(query)
    if ids:
        listing.assert_called_once_with(intervention_ids=ids, session=session)
        session.commit.assert_called_once()
    else:
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
            session=session, now=lambda: datetime(1970, 1, 1, tzinfo=timezone.utc)
        )
    session.rollback.assert_called_once()
    assert caught.value.__cause__ is error
