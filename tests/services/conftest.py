import pytest

from normative_conformance.models.case import CaseLog
from normative_conformance.models.case import ExperimentConfig
from normative_conformance.models.observation import Observation


@pytest.fixture
def add_observation(*, session):
    session.add(ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(CaseLog(case_id="case", created_at_us=0))
    session.commit()
    count = 0

    def add_observation(
        *, start, end, speaker="configured-subject", transcript="hello", level=-30.0, received=0
    ):
        nonlocal count
        count += 1
        observation = Observation(
            case_id="case",
            observation_id=str(count),
            sequence=count,
            speaker_id=speaker,
            start_at_us=round(start * 1_000_000),
            end_at_us=round(end * 1_000_000),
            received_at_us=round(received * 1_000_000),
            transcript=transcript,
            signal_level_min=-60.0,
            signal_level_avg=level,
            signal_level_max=0.0,
        )
        session.add(observation)
        session.commit()
        return observation

    return add_observation
