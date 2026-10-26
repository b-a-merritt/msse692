from typing import Annotated
from typing import Generic
from typing import TypeVar

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


# A nonempty identity that can appear in a URL path segment.
Identifier = Annotated[str, Field(strict=True, min_length=1, pattern=r"^[^/]+$")]

T = TypeVar("T")


class ListResponse(ContractModel, Generic[T]):
    items: list[T]
