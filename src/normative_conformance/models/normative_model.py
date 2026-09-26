from typing import ClassVar

from sqlalchemy import Text
from sqlmodel import Field
from sqlmodel import SQLModel


class NormativeModelVersion(SQLModel, table=True):
    __tablename__: ClassVar[str] = "normative_model_version"

    model_id: str = Field(primary_key=True, sa_type=Text)
    name: str = Field(sa_type=Text)
    version: str = Field(primary_key=True, sa_type=Text)
    type: str = Field(default="undesired", sa_type=Text)
    repairable: bool = True
    rules_json: str = Field(sa_type=Text)
    parameters_json: str = Field(sa_type=Text)
