from sqlmodel import Session

from normative_conformance.services.observation.load_case_speech import load_case_speech


def speaker_labels(*, case_id: str, session: Session) -> list[str]:
    """Use speech order, with stable tie breakers for overlapping observations."""
    speech = sorted(
        load_case_speech(case_id=case_id, session=session),
        key=lambda row: (row.observation.start_at, row.observation.end_at, row.sequence),
    )
    return [row.observation.speaker_id for row in speech]
