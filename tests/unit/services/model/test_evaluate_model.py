from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from normative_conformance.errors import StorageUnavailable
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.model import ModelVersion
from normative_conformance.services.model.evaluate_model import evaluate_model


@pytest.mark.parametrize(
    "after",
    [
        None,
        Observation(
            case_id="case", observation_id="repair", sequence=2, start_at_us=10, end_at_us=20
        ),
    ],
)
def test_runtime_bounds_override_model_parameters_and_lists_are_serialized(*, after):
    model = ModelVersion(
        model_id="rule",
        name="Rule",
        version="1",
        type="undesired",
        rules=[
            {"rule_id": "one", "description": "First", "sql": "SELECT :terms"},
            {"rule_id": "two", "description": "Second", "sql": "SELECT :threshold"},
        ],
        parameters={"terms": ["hello", None], "threshold": 3, "case_id": "incorrect"},
    )
    session = Mock(spec=Session)
    session.exec.return_value.first.return_value = (1,)

    assert evaluate_model(
        model=model,
        case_id="case",
        subject_speaker_id="subject",
        through_sequence=7,
        session=session,
        after_observation=after,
        deadline_at_us=100,
        observation_sequence=4,
    )

    assert [str(call.args[0]) for call in session.exec.call_args_list] == [
        "SELECT :terms",
        "SELECT :threshold",
    ]
    assert session.exec.call_args.kwargs["params"] == {
        "terms": '["hello", null]',
        "threshold": 3,
        "case_id": "case",
        "subject_speaker_id": "subject",
        "through_sequence": 7,
        "after_start_at_us": 10 if after else None,
        "after_end_at_us": 20 if after else None,
        "after_sequence": 2 if after else None,
        "deadline_at_us": 100,
        "observation_sequence": 4,
    }
    session.commit.assert_not_called()


def test_first_nonmatching_rule_short_circuits_remaining_rules():
    model = ModelVersion(
        model_id="rule",
        name="Rule",
        version="1",
        type="undesired",
        rules=[
            {"rule_id": "one", "description": "", "sql": "SELECT 1"},
            {"rule_id": "two", "description": "", "sql": "SELECT 2"},
        ],
        parameters={},
    )
    session = Mock(spec=Session)
    session.exec.return_value.first.return_value = None
    assert not evaluate_model(
        model=model,
        case_id="case",
        subject_speaker_id="subject",
        through_sequence=1,
        session=session,
    )
    assert session.exec.call_count == 1


def test_query_failure_is_translated_without_exposing_driver_details():
    model = ModelVersion(
        model_id="rule",
        name="Rule",
        version="1",
        type="undesired",
        rules=[{"rule_id": "one", "description": "", "sql": "SELECT 1"}],
        parameters={},
    )
    failure = SQLAlchemyError("Private driver details")
    session = Mock(spec=Session)
    session.exec.side_effect = failure
    with pytest.raises(StorageUnavailable, match=r"^The model could not be evaluated$") as caught:
        evaluate_model(
            model=model,
            case_id="case",
            subject_speaker_id="subject",
            through_sequence=1,
            session=session,
        )
    assert caught.value.__cause__ is failure
