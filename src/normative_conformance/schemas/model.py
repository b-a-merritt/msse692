from typing import Annotated
from typing import Literal

from pydantic import Field

from normative_conformance.schemas.common import ContractModel


class ModelRule(ContractModel):
    rule_id: str = Field(strict=True, min_length=1, pattern=r"^[^/]+$")
    description: str
    sql: str = Field(strict=True, min_length=1)


class ModelVersion(ContractModel):
    """A versioned model whose rules identify undesired behavior or repairs."""

    model_id: str = Field(strict=True, min_length=1, pattern=r"^[^/]+$")
    name: str
    version: str = Field(strict=True, min_length=1)
    type: Literal["undesired", "repairs"]
    repairable: bool = Field(strict=True)
    rules: list[ModelRule] = Field(min_length=1)
    parameters: dict[
        Annotated[str, Field(strict=True, min_length=1, pattern=r"^[^/]+$")],
        str | int | float | bool | list[str | int | float | bool | None] | None,
    ]


class ModelList(ContractModel):
    items: list[ModelVersion]
