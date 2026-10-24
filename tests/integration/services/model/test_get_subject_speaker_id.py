from normative_conformance.models.case import CaseLog
from normative_conformance.services.model.get_subject_speaker_id import get_subject_speaker_id


def test_reads_targets_independently_from_storage(session):
    session.add_all(
        [
            CaseLog(case_id="first", created_at_us=0, target_speaker_id="B"),
            CaseLog(case_id="second", created_at_us=1, target_speaker_id="A"),
            CaseLog(case_id="unresolved", created_at_us=2),
        ]
    )
    session.commit()
    session.expunge_all()
    assert get_subject_speaker_id(case_id="first", session=session) == "B"
    assert get_subject_speaker_id(case_id="second", session=session) == "A"
    assert get_subject_speaker_id(case_id="unresolved", session=session) is None
