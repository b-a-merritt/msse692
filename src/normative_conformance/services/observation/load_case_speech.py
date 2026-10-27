from dataclasses import dataclass

from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance.models.observation import Observation
from normative_conformance.models.speaker_revision import ReplacedObservation
from normative_conformance.schemas.observation import ObservationInput
from normative_conformance.schemas.observation import ObservationReplacement
from normative_conformance.services.observation.records import to_input


@dataclass(frozen=True)
class IngestedObservation:
    sequence: int
    observation: ObservationInput


@dataclass(frozen=True)
class CaseSpeech:
    ingested: list[IngestedObservation]
    revisions: list[ObservationReplacement]
    observation_keys: dict[str, int]


def load_case_speech(*, case_id: str, session: Session) -> CaseSpeech:
    """Read ingested speech and speaker revisions in arrival order."""
    # Ingested speech has no revision, so it sorts first and in sequence order.
    rows = session.exec(
        select(Observation)
        .where(Observation.case_id == case_id)
        .order_by(
            col(Observation.speaker_revision_id),
            col(Observation.sequence),
            col(Observation.observation_key),
        )
    ).all()
    ingested = [row for row in rows if row.speaker_revision_id is None]
    revised = [row for row in rows if row.speaker_revision_id is not None]
    replaced: dict[int, list[str]] = {}
    for revision_id, observation_id in session.exec(
        select(ReplacedObservation.speaker_revision_id, Observation.observation_id)
        .join(Observation)
        .where(Observation.case_id == case_id)
        .order_by(col(ReplacedObservation.speaker_revision_id))
    ):
        replaced.setdefault(revision_id, []).append(observation_id)
    replacements: dict[int | None, list[ObservationInput]] = {}
    for row in revised:
        replacements.setdefault(row.speaker_revision_id, []).append(to_input(observation=row))
    # IDs include their turn, so the latest row with an ID is the one a snapshot can use.
    keys: dict[str, int] = {}
    for row in rows:
        assert row.observation_key is not None
        keys[row.observation_id] = row.observation_key
    return CaseSpeech(
        ingested=[_ingested(row) for row in ingested],
        revisions=[
            ObservationReplacement(
                replaced_observation_ids=ids, observations=replacements.get(revision_id, [])
            )
            for revision_id, ids in replaced.items()
        ],
        observation_keys=keys,
    )


def _ingested(row: Observation) -> IngestedObservation:
    assert row.sequence is not None
    return IngestedObservation(sequence=row.sequence, observation=to_input(observation=row))
