from datetime import datetime
from datetime import timezone

from normative_conformance.database import read_session
from normative_conformance.database import write_session
from normative_conformance.models.case import ConversationCase
from normative_conformance.models.observation import Observation
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.schemas.observation import ObservationReplacement
from normative_conformance.services.capture.store_revisions import store_revisions
from normative_conformance.services.observation.load_case_speech import load_case_speech


def test_speech_is_read_as_ingested_in_sequence_order_without_corrections(engine):
    speech = {
        "start_at_us": 0,
        "end_at_us": 1_000_000,
        "transcript": "Hello",
        "signal_level_min": -40,
        "signal_level_avg": -30,
        "signal_level_max": -20,
    }
    with write_session(engine=engine) as session:
        session.add_all(
            [
                ConversationCase(case_id="case", created_at_us=0),
                ConversationCase(case_id="other", created_at_us=0),
            ]
        )
        session.flush()
        session.add_all(
            [
                Observation(
                    case_id="case",
                    observation_id="second",
                    sequence=2,
                    received_at_us=20,
                    speaker_id="B",
                    **speech,
                ),
                Observation(
                    case_id="case",
                    observation_id="first",
                    sequence=1,
                    received_at_us=10,
                    speaker_id="A",
                    **speech,
                ),
                Observation(
                    case_id="other",
                    observation_id="first",
                    sequence=1,
                    received_at_us=10,
                    speaker_id="A",
                    **speech,
                ),
            ]
        )
        session.commit()
    store_revisions(
        case_id="case",
        replacements=[
            ObservationReplacement(
                replaced_observation_ids=["first"],
                observations=[
                    ObservationInput(
                        case_id="case",
                        observation_id="first-C",
                        speaker_id="C",
                        start_at="1970-01-01T00:00:00Z",
                        end_at="1970-01-01T00:00:01Z",
                        transcript="Hello",
                        signal_level_min=-40,
                        signal_level_avg=-30,
                        signal_level_max=-20,
                    )
                ],
            )
        ],
        engine=engine,
        now=lambda: datetime(1970, 1, 1, second=5, tzinfo=timezone.utc),
    )

    with read_session(engine=engine) as session:
        rows = load_case_speech(case_id="case", session=session)

    assert [
        (row.sequence, row.observation.observation_id, row.observation.speaker_id) for row in rows
    ] == [(1, "first", "A"), (2, "second", "B")]
    assert len({row.observation_key for row in rows}) == 2
