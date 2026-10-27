from pydantic import AwareDatetime

from normative_conformance.schemas.common import ContractModel
from normative_conformance.schemas.decision import Action


class ObservationDecision(ContractModel):
    observation_id: str
    topic_scores: dict[str, float]
    topics: list[str]
    primary_topic: str
    behavior_scores: dict[str, float]
    behaviors: list[str]
    intensity: float | None


class Assessment(ContractModel):
    model: str
    prompt_version: str
    selection_threshold: float
    observations: list[ObservationDecision]
    action: Action
    action_probabilities: dict[str, float]
    action_confidence: float
    assessment_id: int
    case_id: str
    target_speaker_id: str
    target_revision: int
    evaluated_at: AwareDatetime
    completed_at: AwareDatetime
    after_sequence: int
    through_sequence: int
