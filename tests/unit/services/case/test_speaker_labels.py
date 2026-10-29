from datetime import UTC
from datetime import datetime
from importlib import import_module

from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.services.observation.load_case_speech import IngestedObservation

module = import_module("normative_conformance.services.case.speaker_labels")


def test_labels_follow_speech_order_with_stable_tie_breakers(monkeypatch):
    first = ObservationInput(
        case_id="case",
        observation_id="first",
        speaker_id="A",
        start_at="1970-01-01T00:00:00Z",
        end_at="1970-01-01T00:00:02Z",
        transcript="Hello",
        signal_level_min=-40,
        signal_level_avg=-30,
        signal_level_max=-20,
    )
    shorter = first.model_copy(
        update={"speaker_id": "B", "end_at": datetime(1970, 1, 1, second=1, tzinfo=UTC)}
    )
    same_times = first.model_copy(update={"speaker_id": "C"})
    # Arrival order: same_times (sequence 1), first (2), shorter (3).
    speech = [
        IngestedObservation(
            observation_key=sequence,
            sequence=sequence,
            received_at=datetime(1970, 1, 1, tzinfo=UTC),
            observation=observation,
        )
        for sequence, observation in [(1, same_times), (2, first), (3, shorter)]
    ]
    monkeypatch.setattr(module, "load_case_speech", lambda *, case_id, session: speech)

    assert module.speaker_labels(case_id="case", session=object()) == ["B", "C", "A"]
