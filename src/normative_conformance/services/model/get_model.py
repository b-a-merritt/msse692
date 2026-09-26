import json

from sqlmodel import Session

from normative_conformance.errors import NotFound
from normative_conformance.models.normative_model import NormativeModelVersion
from normative_conformance.schemas.model import ModelVersion


def get_model(
    *,
    model_id: str,
    version: str,
    session: Session,
) -> ModelVersion:
    row = session.get(NormativeModelVersion, (model_id, version))

    if row is None:
        raise NotFound("The model was not found")

    return ModelVersion.model_validate(
        {
            **row.model_dump(exclude={"rules_json", "parameters_json"}),
            "rules": json.loads(row.rules_json),
            "parameters": json.loads(row.parameters_json),
        },
    )
