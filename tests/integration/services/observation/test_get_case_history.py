from itertools import count

from normative_conformance import models
from normative_conformance.models.case import CaseLog
from normative_conformance.models.observation import Observation
from normative_conformance.services.observation.get_case_history import get_case_history

from ...storage import persist


def test_reads_only_the_requested_case_prefix_in_sequence_order(*, session):
    session.add(models.ExperimentConfig(subject_speaker_id="configured-subject", created_at_us=0))
    session.add(models.CaseLog(case_id="case", created_at_us=0))
    session.commit()
    observation_sequences = count(1)

    first = persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=3_000_000,
            end_at_us=4_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    second = persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=1_000_000,
            end_at_us=2_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    persist(
        session=session,
        record=models.Observation(
            case_id="case",
            observation_id=str(observation_sequence := next(observation_sequences)),
            sequence=observation_sequence,
            speaker_id="configured-subject",
            start_at_us=5_000_000,
            end_at_us=6_000_000,
            received_at_us=0,
            transcript="hello",
            signal_level_min=-60.0,
            signal_level_avg=-30.0,
            signal_level_max=0.0,
        ),
    )
    session.add(CaseLog(case_id="other", created_at_us=0))
    session.flush()
    session.add(Observation(**(first.model_dump() | {"case_id": "other"})))
    session.commit()

    history = get_case_history(case_id="case", through_sequence=2, session=session)

    assert history == [first, second]


def test_unknown_case_has_no_history(*, session):
    assert get_case_history(case_id="missing", through_sequence=1, session=session) == []
