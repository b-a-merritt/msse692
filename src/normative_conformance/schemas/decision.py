from typing import Literal

from pydantic import AwareDatetime

from normative_conformance.schemas.common import ContractModel
from normative_conformance.schemas.observation import ObservationInput

Action = Literal["remain_silent", "await_context", "reflect_later", "intervene"]


class DecisionSnapshot(ContractModel):
    case_id: str
    target_speaker_id: str
    target_revision: int
    after_sequence: int
    through_sequence: int
    captured_at: AwareDatetime
    observations: list[ObservationInput]
    new_observation_ids: list[str]


class ObservationAnswers(ContractModel):
    """The model's answers about one turn of new speech, before any threshold is applied.

    `observation_id` is the turn's first observation.
    """

    observation_id: str
    topic_scores: dict[str, float]
    primary_topic: str
    behavior_scores: dict[str, float]
    intensity: float | None


class DecisionAnswers(ContractModel):
    """The model's answers for one batch, before any threshold is applied."""

    model: str
    prompt_version: str
    observations: list[ObservationAnswers]
    # Batches without new target speech are not asked for an action.
    action: Action | None
    action_probabilities: dict[str, float]
    action_confidence: float | None
