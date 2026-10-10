from unittest.mock import Mock

import pytest
from sqlmodel import Session

from normative_conformance.services.intervention.list_interventions import list_interventions


@pytest.mark.parametrize(
    "case_id,status,ids", [(None, None, None), ("case", "pending", [2, 5]), ("case", "sent", [])]
)
def test_builds_optional_filters_without_mutating_storage(*, case_id, status, ids):
    session = Mock(spec=Session)
    rows = [object()]
    session.exec.return_value.all.return_value = rows
    assert (
        list_interventions(session=session, case_id=case_id, status=status, intervention_ids=ids)
        == rows
    )
    query = session.exec.call_args.args[0].compile()
    if case_id is not None:
        assert query.params["case_id_1"] == "case"
    if ids is not None:
        assert query.params["intervention_id_1"] == ids
    if status == "pending":
        assert "sent_at_us IS NULL" in str(query)
    elif status == "sent":
        assert "sent_at_us IS NOT NULL" in str(query)
    else:
        assert "WHERE" not in str(query)
    assert "ORDER BY intervention.intervention_id" in str(query)
    session.commit.assert_not_called()
