from typing import Literal

from conversation_monitor.schemas.common import ContractModel


class Liveness(ContractModel):
    status: Literal["live"]


class Readiness(ContractModel):
    status: Literal["ready"]
