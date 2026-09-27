from dataclasses import replace

import pytest

from normative_conformance.services.assessment.create_assessment import create_assessment
from normative_conformance.services.assessment.get_last_repair import get_last_repair
from normative_conformance.services.model.get_model import get_model


@pytest.mark.parametrize(
    "intervals,expected",
    [([(3, 4), (1, 2)], 0), ([(1, 4), (1, 2)], 0), ([(1, 2), (1, 2)], 1)],
)
def test_recorded_repair_uses_speech_order_with_sequence_as_tiebreaker(
    *, add_observation, snapshot, session, intervals, expected
):
    observations = [
        add_observation(start=start, end=end, transcript="I apologize", received=100 + index)
        for index, (start, end) in enumerate(intervals)
    ]
    assert get_last_repair(case_id="case", session=session) is None
    model = get_model(model_id="apology", version="1", session=session)
    for observation in observations:
        create_assessment(
            model=model,
            snapshot=replace(snapshot(at=110), through_sequence=observation.sequence),
            status="conformant",
            session=session,
        )
    add_observation(start=10, end=11, transcript="I apologize", received=102)

    assert get_last_repair(case_id="case", session=session) == observations[expected]
    assert get_last_repair(case_id="other", session=session) is None
