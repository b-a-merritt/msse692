from pydantic import AwareDatetime

from normative_conformance.schemas.common import ContractModel


class CaseTrace(ContractModel):
    """A case's trace for its current target, and the assessments it came from."""

    events: list[str]
    assessment_ids: list[int]


class DiscoveredModel(ContractModel):
    normative_model_id: int
    discovered_at: AwareDatetime
    topics: list[str]
