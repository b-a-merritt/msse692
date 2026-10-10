from importlib import import_module
from unittest.mock import Mock

import pytest
from sqlmodel import Session

from normative_conformance.models.observation import Observation
from normative_conformance.schemas.model import ModelVersion

module = import_module("normative_conformance.services.model.find_repair")


@pytest.mark.parametrize("matches,expected_index", [([False, True], 1), ([False, False], None)])
def test_search_stops_at_first_matching_observation_and_preserves_bounds(
    *, monkeypatch, matches, expected_index
):
    model = ModelVersion(
        model_id="apology",
        name="Apology",
        version="1",
        type="repairs",
        rules=[{"rule_id": "one", "description": "", "sql": "SELECT 1"}],
        parameters={},
    )
    observations = [
        Observation(
            case_id="case", observation_id="newer", sequence=5, start_at_us=50, end_at_us=60
        ),
        Observation(
            case_id="case", observation_id="older", sequence=3, start_at_us=10, end_at_us=20
        ),
    ]
    session = Mock(spec=Session)
    session.exec.return_value = iter(observations)
    evaluate = Mock(side_effect=matches)
    monkeypatch.setattr(module, "evaluate_model", evaluate)
    after = Observation(case_id="case", observation_id="previous", sequence=1)

    result = module.find_repair(
        models=[model],
        case_id="case",
        subject_speaker_id="subject",
        through_sequence=5,
        session=session,
        after_observation=after,
        deadline_at_us=100,
    )

    assert result == (None if expected_index is None else (model, observations[expected_index]))
    assert [call.kwargs["observation_sequence"] for call in evaluate.call_args_list] == [5, 3]
    for call in evaluate.call_args_list:
        assert call.kwargs["deadline_at_us"] == 100
        assert call.kwargs["after_observation"] is after
        assert call.kwargs["through_sequence"] == 5
    query = session.exec.call_args.args[0].compile()
    assert query.params == {"case_id_1": "case", "sequence_1": 5}
    assert "start_at_us DESC, observation.end_at_us DESC, observation.sequence DESC" in str(query)


def test_empty_history_never_evaluates_rules(*, monkeypatch):
    session = Mock(spec=Session)
    session.exec.return_value = []
    evaluate = Mock()
    monkeypatch.setattr(module, "evaluate_model", evaluate)
    assert (
        module.find_repair(
            models=[],
            case_id="case",
            subject_speaker_id="subject",
            through_sequence=1,
            session=session,
        )
        is None
    )
    evaluate.assert_not_called()
