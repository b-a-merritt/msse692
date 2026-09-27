from typing import Generic
from typing import TypeVar

from pydantic import BaseModel
from pydantic import ConfigDict


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


T = TypeVar("T")


class ListResponse(ContractModel, Generic[T]):
    items: list[T]
