from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from normative_conformance.models.assessment import Assessment
from normative_conformance.models.normative_model import NormativeModelVersion
from normative_conformance.models.observation import Observation


def get_last_repair(*, case_id: str, session: Session) -> Observation | None:
    return session.exec(
        select(Observation)
        .join(
            Assessment,
            (col(Assessment.case_id) == Observation.case_id)
            & (col(Assessment.through_sequence) == Observation.sequence),
        )
        .join(
            NormativeModelVersion,
            (col(NormativeModelVersion.model_id) == Assessment.model_id)
            & (col(NormativeModelVersion.version) == Assessment.model_version),
        )
        .where(
            Observation.case_id == case_id,
            NormativeModelVersion.type == "repairs",
            Assessment.status == "conformant",
        )
        .order_by(
            col(Observation.start_at_us).desc(),
            col(Observation.end_at_us).desc(),
            col(Observation.sequence).desc(),
        )
        .limit(1)
    ).first()
