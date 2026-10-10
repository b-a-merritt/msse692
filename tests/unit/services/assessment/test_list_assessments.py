from unittest.mock import Mock

import pytest
from sqlmodel import Session

from normative_conformance.services.assessment.list_assessments import list_assessments


@pytest.mark.parametrize("filtered", [False, True])
def test_optional_identity_status_and_resolution_filters(*, filtered):
    session = Mock(spec=Session)
    rows = [object()]
    session.exec.return_value.all.return_value = rows
    assert (
        list_assessments(
            session=session,
            case_id="case" if filtered else None,
            evaluation_id="evaluation" if filtered else None,
            status="pending" if filtered else None,
            unresolved=filtered,
        )
        == rows
    )
    query = session.exec.call_args.args[0].compile()
    if filtered:
        assert query.params == {
            "case_id_1": "case",
            "evaluation_id_1": "evaluation",
            "status_1": "pending",
        }
        assert "NOT IN" in str(query)
        assert "resolves_assessment_id IS NOT NULL" in str(query)
    else:
        assert "WHERE" not in str(query)
    assert "ORDER BY assessment.assessment_id" in str(query)
    session.commit.assert_not_called()
