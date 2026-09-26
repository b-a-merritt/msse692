from typing import Literal

from normative_conformance.schemas.common import ContractModel


class Liveness(ContractModel):
    status: Literal["live"]


class Readiness(ContractModel):
    status: Literal["ready"]
