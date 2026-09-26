import json

from sqlmodel import Session
from sqlmodel import select

from normative_conformance.models.normative_model import NormativeModelVersion
from normative_conformance.schemas.model import ModelList
from normative_conformance.schemas.model import ModelVersion


def list_models(
    *,
    session: Session,
) -> ModelList:
    """Read the complete fixed catalog ordered by model_id and version."""
    rows = session.exec(
        select(NormativeModelVersion).order_by(
            NormativeModelVersion.model_id,
            NormativeModelVersion.version,
        )
    ).all()

    return ModelList(
        items=[
            ModelVersion.model_validate(
                {
                    **row.model_dump(exclude={"rules_json", "parameters_json"}),
                    "rules": json.loads(row.rules_json),
                    "parameters": json.loads(row.parameters_json),
                },
            )
            for row in rows
        ]
    )
