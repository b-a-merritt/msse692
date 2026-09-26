from typing import Annotated

from pydantic import Field

from normative_conformance.schemas.common import ContractModel


class ModelRule(ContractModel):
    rule_id: str = Field(strict=True, min_length=1, pattern=r"^[^/]+$")
    description: str
    sql: str = Field(strict=True, min_length=1)


class ModelVersion(ContractModel):
    """A versioned definition of an undesirable behavior pattern."""

    model_id: str = Field(strict=True, min_length=1, pattern=r"^[^/]+$")
    name: str
    version: str = Field(strict=True, min_length=1)
    subject_speaker_id: str = Field(strict=True, min_length=1, pattern=r"^[^/]+$")
    rules: list[ModelRule] = Field(min_length=1)
    parameters: dict[
        Annotated[str, Field(strict=True, min_length=1, pattern=r"^[^/]+$")],
        str | int | float | bool | list[str | int | float | bool | None] | None,
    ]


class ModelList(ContractModel):
    items: list[ModelVersion]
