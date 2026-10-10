from datetime import datetime
from datetime import timezone
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from normative_conformance.errors import StorageUnavailable
from normative_conformance.models.assessment import Assessment
from normative_conformance.models.intervention import Intervention
from normative_conformance.services.intervention.create_intervention import create_intervention


@pytest.mark.parametrize(
    "model_ids,message",
    [
        (
            ["high_intensity_address", "repeated_interruption", "harm_phrase"],
            "You're talking over them with a raised voice. Pause and let them finish.",
        ),
        (
            ["extended_turn", "harm_phrase"],
            "You said something that could be heard as a threat. "
            "Take a moment before you continue.",
        ),
        (["extended_turn"], "You've been speaking for a while. Pause and ask for their view."),
    ],
)
def test_selects_highest_priority_message_and_links_every_source(*, model_ids, message):
    session = Mock(spec=Session)
    session.exec.return_value.all.return_value = [
        Assessment(assessment_id=index, model_id=model_id)
        for index, model_id in enumerate(model_ids, start=1)
    ]
    stored = []
    sources = []
    session.add.side_effect = stored.append
    session.flush.side_effect = lambda: setattr(stored[0], "intervention_id", 9)
    session.add_all.side_effect = lambda rows: sources.extend(rows)
    create_intervention(
        case_id="case",
        since_us=90,
        session=session,
        now=lambda: datetime(1970, 1, 1, 0, 0, 0, 100, tzinfo=timezone.utc),
    )
    assert len(stored) == 1
    assert isinstance(stored[0], Intervention)
    assert stored[0].message == message
    assert stored[0].case_id == "case"
    assert stored[0].created_at_us == 100
    assert [(row.intervention_id, row.assessment_id) for row in sources] == [
        (9, index) for index in range(1, len(model_ids) + 1)
    ]
    session.commit.assert_called_once()
    session.rollback.assert_not_called()
    query = session.exec.call_args.args[0].compile()
    assert query.params["case_id_1"] == "case"
    assert query.params["evaluated_at_us_1"] == 90
    assert query.params["status_1"] == "conformant"
    assert query.params["type_1"] == "undesired"
    assert "NOT IN" in str(query)


def test_no_eligible_sources_does_not_read_clock_or_write():
    session = Mock(spec=Session)
    session.exec.return_value.all.return_value = []
    clock = Mock()
    assert create_intervention(case_id="case", since_us=90, session=session, now=clock) is None
    clock.assert_not_called()
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_unrecognized_combination_fails_before_writing():
    session = Mock(spec=Session)
    session.exec.return_value.all.return_value = [Assessment(assessment_id=1, model_id="unknown")]
    with pytest.raises(LookupError, match=r"^No intervention message matches the assessments$"):
        create_intervention(case_id="case", since_us=90, session=session, now=Mock())
    session.add.assert_not_called()


def test_storage_failure_rolls_back_and_preserves_driver_cause():
    session = Mock(spec=Session)
    error = SQLAlchemyError("Private driver details")
    session.exec.side_effect = error
    with pytest.raises(
        StorageUnavailable, match=r"^The intervention could not be created$"
    ) as caught:
        create_intervention(case_id="case", since_us=90, session=session, now=Mock())
    assert caught.value.__cause__ is error
    session.rollback.assert_called_once()
    session.commit.assert_not_called()
