from normative_conformance.models.observation import Observation
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.schemas.observation import ObservationRecord
from normative_conformance.timestamps import from_microseconds


def to_input(*, observation: Observation) -> ObservationInput:
    return ObservationInput(
        case_id=observation.case_id,
        observation_id=observation.observation_id,
        speaker_id=observation.speaker_id,
        start_at=from_microseconds(value=observation.start_at_us),
        end_at=from_microseconds(value=observation.end_at_us),
        transcript=observation.transcript,
        signal_level_min=observation.signal_level_min,
        signal_level_avg=observation.signal_level_avg,
        signal_level_max=observation.signal_level_max,
    )


def to_record(*, observation: Observation) -> ObservationRecord:
    """Convert ingested speech, which always has a sequence and receipt time."""
    assert observation.sequence is not None and observation.received_at_us is not None
    received_at = from_microseconds(value=observation.received_at_us)
    return ObservationRecord(
        **to_input(observation=observation).model_dump(),
        received_at=received_at,
        updated_at=received_at,
        sequence=observation.sequence,
    )
