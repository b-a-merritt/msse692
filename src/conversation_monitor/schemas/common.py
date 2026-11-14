from typing import Annotated
from typing import Generic
from typing import TypeVar

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


# Identities reach the decision model, so they exclude the spaces that free text needs.
IDENTIFIER_PATTERN = r"^[A-Za-z0-9._:-]+$"
IDENTIFIER_MAX_LENGTH = 128
Identifier = Annotated[
    str,
    Field(strict=True, min_length=1, max_length=IDENTIFIER_MAX_LENGTH, pattern=IDENTIFIER_PATTERN),
]

T = TypeVar("T")


class ListResponse(ContractModel, Generic[T]):
    items: list[T]
