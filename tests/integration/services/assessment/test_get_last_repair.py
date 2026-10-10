from dataclasses import replace
from itertools import count
from uuid import uuid4

import pytest

from normative_conformance import models
from normative_conformance.schemas.assessment import CaseSnapshot
from normative_conformance.services.assessment.create_assessment import create_assessment
from normative_conformance.services.assessment.get_last_repair import get_last_repair
from normative_conformance.services.model.get_model import get_model
from normative_conformance.services.observation.get_case_sequence import get_case_sequence

from ...storage import persist


@pytest.mark.parametrize(
    "intervals,expected",
    [([(3, 4), (1, 2)], 0), ([(1, 4), (1, 2)], 0), ([(1, 2), (1, 2)], 1)],
)
def test_recorded_repair_uses_speech_order_with_sequence_as_tiebreaker(
    *, session, intervals, expected
):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)

    observations = [
        persist(
            session=session,
            record=models.Observation(
                case_id="case",
                observation_id=str(observation_sequence := next(observation_sequences)),
                sequence=observation_sequence,
                speaker_id="configured-subject",
                start_at_us=round((start) * 1_000_000),
                end_at_us=round((end) * 1_000_000),
                received_at_us=round((100 + index) * 1_000_000),
                transcript="I apologize",
                signal_level_min=-60.0,
                signal_level_avg=-30.0,
                signal_level_max=0.0,
            ),
        )
        for index, (start, end) in enumerate(intervals)
    ]
    assert get_last_repair(case_id="case", session=session) is None
    model = get_model(model_id="apology", version="1", session=session)
    for observation in observations:
        create_assessment(
            model=model,
            snapshot=replace(
                CaseSnapshot(
                    case_id="case",
                    evaluation_id=str(uuid4()),
                    through_sequence=get_case_sequence(case_id="case", session=session),
                    evaluated_at_us=110_000_000,
                ),
                through_sequence=observation.sequence,
            ),
            status="conformant",
            session=session,
        )
    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=10_000_000,
            end_at_us=11_000_000,
            received_at_us=102_000_000,
            transcript="I apologize",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )

    assert get_last_repair(case_id="case", session=session) == observations[expected]
    assert get_last_repair(case_id="other", session=session) is None
