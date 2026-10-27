from normative_conformance.models.observation import Observation
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.schemas.observation import ObservationRecord
from normative_conformance.timestamps import from_microseconds
from normative_conformance.timestamps import to_microseconds


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


def to_row(
    *,
    observation: ObservationInput,
    sequence: int | None = None,
    received_at_us: int | None = None,
    speaker_revision_id: int | None = None,
) -> Observation:
    """Ingested speech has a sequence and receipt time; revised speech has its revision."""
    return Observation(
        case_id=observation.case_id,
        observation_id=observation.observation_id,
        speaker_revision_id=speaker_revision_id,
        sequence=sequence,
        received_at_us=received_at_us,
        speaker_id=observation.speaker_id,
        start_at_us=to_microseconds(value=observation.start_at),
        end_at_us=to_microseconds(value=observation.end_at),
        transcript=observation.transcript,
        signal_level_min=observation.signal_level_min,
        signal_level_avg=observation.signal_level_avg,
        signal_level_max=observation.signal_level_max,
    )


def to_record(*, observation: Observation) -> ObservationRecord:
    """Convert ingested speech, which always has a sequence and receipt time."""
    assert observation.sequence is not None and observation.received_at_us is not None
    return ObservationRecord(
        **to_input(observation=observation).model_dump(),
        received_at=from_microseconds(value=observation.received_at_us),
        sequence=observation.sequence,
    )
