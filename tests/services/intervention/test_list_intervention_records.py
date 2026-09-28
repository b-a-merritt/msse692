"""Intervention reads filter by case and delivery status without changing records."""

from sqlmodel import select

from normative_conformance import models
from normative_conformance.services.intervention.list_intervention_records import (
    list_intervention_records,
)
from normative_conformance.services.intervention.list_interventions import list_interventions

from .conftest import at


def test_no_interventions_returns_an_empty_list(*, session, add_assessment):
    assert list_intervention_records(session=session) == []


def test_interventions_are_listed_in_id_order_with_sorted_sources(
    *, session, add_assessment, create
):
    first = add_assessment(model_id="harm_phrase")
    create()
    later = [
        add_assessment(model_id="high_intensity_address", at=103),
        add_assessment(model_id="repeated_interruption", at=103),
    ]
    create(since=103, now=105)

    records = list_intervention_records(session=session)
    assert [record.assessment_ids for record in records] == [
        [first.assessment_id],
        [assessment.assessment_id for assessment in later],
    ]
    assert [record.created_at for record in records] == [at(102), at(105)]


def test_status_is_derived_from_the_sent_time(*, session, add_assessment, create):
    add_assessment(model_id="harm_phrase")
    create()
    sent = list_interventions(session=session)[0]
    add_assessment(model_id="extended_turn", at=103)
    create(since=103, now=105)
    pending = list_interventions(session=session)[-1]
    sent.sent_at_us = 106_000_000
    session.commit()

    assert [
        (record.intervention_id, record.status, record.sent_at)
        for record in list_intervention_records(session=session)
    ] == [(sent.intervention_id, "sent", at(106)), (pending.intervention_id, "pending", None)]
    assert [
        record.intervention_id
        for record in list_intervention_records(status="sent", session=session)
    ] == [sent.intervention_id]
    assert [
        record.intervention_id
        for record in list_intervention_records(status="pending", session=session)
    ] == [pending.intervention_id]


def test_filters_by_case_and_ids(*, session, add_assessment, create):
    add_assessment(model_id="harm_phrase")
    create()
    record = list_intervention_records(session=session)[0]
    assert list_intervention_records(case_id="case", session=session) == [record]
    assert list_intervention_records(case_id="other", session=session) == []
    assert list_intervention_records(
        intervention_ids=[record.intervention_id], session=session
    ) == [record]
    assert (
        list_intervention_records(intervention_ids=[record.intervention_id + 1], session=session)
        == []
    )
    assert list_intervention_records(intervention_ids=[], session=session) == []


def test_listing_does_not_mark_interventions_sent(*, session, add_assessment, create):
    add_assessment(model_id="harm_phrase")
    create()
    list_intervention_records(session=session)
    assert [row.sent_at_us for row in session.exec(select(models.Intervention))] == [None]
