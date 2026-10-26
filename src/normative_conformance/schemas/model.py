from typing import Literal

from pydantic import Field

from normative_conformance.schemas.common import ContractModel
from normative_conformance.schemas.common import Identifier


class ModelRule(ContractModel):
    rule_id: Identifier
    description: str
    sql: str = Field(strict=True, min_length=1)


class ModelVersion(ContractModel):
    """A versioned model whose rules identify undesired behavior or repairs."""

    model_id: Identifier
    name: str
    version: str = Field(strict=True, min_length=1)
    type: Literal["undesired", "repairs"]
    repair_allowance_us: int | None = Field(default=None, strict=True, gt=0)
    rules: list[ModelRule] = Field(min_length=1)
    parameters: dict[
        Identifier,
        str | int | float | bool | list[str | int | float | bool | None] | None,
    ]
