from sqlmodel import Session

from normative_conformance.errors import NotFound
from normative_conformance.models.normative_model import NormativeModelVersion
from normative_conformance.schemas.model import ModelVersion
from normative_conformance.services.model.records import to_model


def get_model(
    *,
    model_id: str,
    version: str,
    session: Session,
) -> ModelVersion:
    row = session.get(NormativeModelVersion, (model_id, version))

    if row is None:
        raise NotFound("The model was not found")

    return to_model(row=row)
