from unittest.mock import Mock

from normative_conformance.routes import case
from normative_conformance.schemas.case import TargetSelection


def test_get_case_passes_requested_identity_to_service(monkeypatch):
    session = object()
    read = Mock()
    monkeypatch.setattr(case, "load_case", read)
    assert case.get_case(case_id="requested", session=session) is read.return_value
    read.assert_called_once_with(case_id="requested", session=session)


def test_select_target_passes_validated_input_and_resources(monkeypatch):
    session, clock = object(), object()
    input = TargetSelection(target_speaker_order=2)
    select = Mock()
    monkeypatch.setattr(case, "store_target", select)
    assert (
        case.select_target(case_id="requested", input=input, session=session, now=clock)
        is select.return_value
    )
    select.assert_called_once_with(case_id="requested", selection=input, session=session, now=clock)
