import pytest

from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.schemas.observation import ObservationRecord
from normative_conformance.schemas.observation import ObservationReplacement
from normative_conformance.services.decision.batch import batch_end


def _stored(*, observation_id, sequence):
    return ObservationRecord(
        case_id="case",
        observation_id=observation_id,
        sequence=sequence,
        speaker_id="A",
        start_at="1970-01-01T00:00:00Z",
        end_at="1970-01-01T00:00:01Z",
        transcript="Hello",
        signal_level_min=-40,
        signal_level_avg=-30,
        signal_level_max=-20,
        received_at="1970-01-01T00:01:00Z",
        updated_at="1970-01-01T00:01:00Z",
    )


@pytest.mark.parametrize(
    "after_sequence,batch_size,expected",
    [
        pytest.param(0, 2, 2, id="first-batch"),
        pytest.param(2, 2, 3, id="last-partial-batch"),
        pytest.param(3, 2, None, id="nothing-new"),
    ],
)
def test_batch_ends_after_up_to_batch_size_new_observations(after_sequence, batch_size, expected):
    observations = [
        _stored(observation_id=name, sequence=sequence)
        for sequence, name in [(3, "three"), (1, "one"), (2, "two")]
    ]
    assert (
        batch_end(
            observations=observations,
            revisions=[],
            after_sequence=after_sequence,
            batch_size=batch_size,
        )
        == expected
    )


@pytest.mark.parametrize(
    "after_sequence,expected",
    [
        pytest.param(0, 3, id="turn-starts-in-batch"),
        pytest.param(1, 3, id="turn-already-partly-handled"),
    ],
)
def test_batch_includes_the_whole_of_a_revised_turn(after_sequence, expected):
    observations = [
        _stored(observation_id=name, sequence=sequence)
        for sequence, name in [(1, "one"), (2, "two"), (3, "three"), (4, "four")]
    ]
    revision = ObservationReplacement(
        replaced_observation_ids=["one", "two", "three"],
        observations=[
            ObservationInput(
                case_id="case",
                observation_id="merged",
                speaker_id="B",
                start_at="1970-01-01T00:00:00Z",
                end_at="1970-01-01T00:00:01Z",
                transcript="Hello",
                signal_level_min=-40,
                signal_level_avg=-30,
                signal_level_max=-20,
            )
        ],
    )
    assert (
        batch_end(
            observations=observations,
            revisions=[revision],
            after_sequence=after_sequence,
            batch_size=1,
        )
        == expected
    )
