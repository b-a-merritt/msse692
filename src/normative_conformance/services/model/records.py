import json

from normative_conformance.models.normative_model import NormativeModelVersion
from normative_conformance.schemas.model import ModelVersion


def to_model(*, row: NormativeModelVersion) -> ModelVersion:
    return ModelVersion.model_validate(
        {
            **row.model_dump(exclude={"rules_json", "parameters_json"}),
            "rules": json.loads(row.rules_json),
            "parameters": json.loads(row.parameters_json),
        },
    )
