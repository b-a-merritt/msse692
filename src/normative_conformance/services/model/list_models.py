from sqlmodel import Session
from sqlmodel import select

from normative_conformance.models.normative_model import NormativeModelVersion
from normative_conformance.schemas.model import ModelVersion
from normative_conformance.services.model.records import to_model


def list_models(
    *,
    session: Session,
) -> list[ModelVersion]:
    """Read the complete fixed catalog ordered by model_id and version."""
    rows = session.exec(
        select(NormativeModelVersion).order_by(
            NormativeModelVersion.model_id,
            NormativeModelVersion.version,
        )
    ).all()
    return [to_model(row=row) for row in rows]
