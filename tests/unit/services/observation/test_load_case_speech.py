from unittest.mock import Mock

from sqlmodel import Session

from normative_conformance.models.observation import Observation
from normative_conformance.models.speaker_revision import ReplacedObservation
from normative_conformance.services.observation.load_case_speech import load_case_speech


def test_groups_corrections_by_revision_and_keys_ids_to_their_latest_rows():
    speech = {
        "speaker_id": "A",
        "start_at_us": 0,
        "end_at_us": 1_000_000,
        "transcript": "Hello",
        "signal_level_min": -40,
        "signal_level_avg": -30,
        "signal_level_max": -20,
    }
    rows = {
        Observation: [
            Observation(
                observation_key=1,
                case_id="case",
                observation_id="turn",
                sequence=1,
                received_at_us=0,
                **speech,
            ),
            Observation(
                observation_key=2,
                case_id="case",
                observation_id="other",
                sequence=2,
                received_at_us=0,
                **speech,
            ),
            Observation(
                observation_key=3,
                case_id="case",
                observation_id="turn",
                speaker_revision_id=5,
                **speech,
            ),
            Observation(
                observation_key=4,
                case_id="case",
                observation_id="turn",
                speaker_revision_id=6,
                **speech,
            ),
        ],
        # A revision may remove speech without adding any.
        ReplacedObservation: [(5, "turn"), (6, "turn"), (7, "other")],
    }
    session = Mock(spec=Session)
    session.exec.side_effect = lambda query: Mock(
        all=Mock(return_value=rows[query.column_descriptions[0]["entity"]]),
        __iter__=lambda self: iter(rows[query.column_descriptions[0]["entity"]]),
    )

    result = load_case_speech(case_id="case", session=session)

    assert [(row.observation_id, row.sequence) for row in result.observations] == [
        ("turn", 1),
        ("other", 2),
    ]
    assert [
        (revision.replaced_observation_ids, [row.observation_id for row in revision.observations])
        for revision in result.revisions
    ] == [(["turn"], ["turn"]), (["turn"], ["turn"]), (["other"], [])]
    assert result.observation_keys == {"turn": 4, "other": 2}
