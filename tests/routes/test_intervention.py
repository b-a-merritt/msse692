from uuid import uuid4

import pytest

from normative_conformance.database import write_session
from normative_conformance.services.assessment.evaluate_case import evaluate_case
from normative_conformance.services.intervention.create_intervention import create_intervention
from normative_conformance.services.intervention.list_intervention_records import (
    list_intervention_records,
)
from normative_conformance.timestamps import to_microseconds

THREAT = "You said something that could be heard as a threat. Take a moment before you continue."


def _create_intervention(*, client, observation_data, received_at):
    response = client.post(
        "/api/v1/observations",
        json=observation_data
        | {
            "speaker_id": client.app.state.settings.subject_speaker_id,
            "transcript": "I hope you die",
        },
    )
    assert response.status_code == 202
    rows = evaluate_case(
        case_id="case",
        evaluation_id=uuid4(),
        engine=client.app.state.engine,
        scheduler=client.app.state.scheduler,
        now=client.app.state.clock,
    )
    with write_session(engine=client.app.state.engine) as session:
        create_intervention(
            case_id="case",
            since_us=to_microseconds(value=received_at),
            session=session,
            now=client.app.state.clock,
        )
        record = list_intervention_records(session=session)[0]
    assert record.assessment_ids == [row.assessment_id for row in rows]
    return record


def _timestamp(value):
    return value.isoformat().replace("+00:00", "Z")


def test_listing_without_interventions_returns_empty_items(*, client):
    response = client.get("/api/v1/interventions")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_delivery_marks_listed_interventions_sent_once(*, client, observation_data, received_at):
    record = _create_intervention(
        client=client, observation_data=observation_data, received_at=received_at
    )
    pending = {
        "intervention_id": record.intervention_id,
        "case_id": "case",
        "subject_speaker_id": client.app.state.settings.subject_speaker_id,
        "assessment_ids": record.assessment_ids,
        "message": THREAT,
        "created_at": _timestamp(received_at),
        "status": "pending",
        "sent_at": None,
    }
    sent = pending | {"status": "sent", "sent_at": _timestamp(received_at)}

    assert client.get("/api/v1/interventions").json() == {"items": [pending]}
    assert client.get("/api/v1/interventions", params={"status": "sent"}).json() == {"items": []}
    # Listing is read-only; only delivery changes the status.
    assert client.get("/api/v1/interventions").json() == {"items": [pending]}

    response = client.post("/api/v1/interventions/deliver")

    assert response.status_code == 200
    assert response.json() == {"items": [sent]}
    assert client.post("/api/v1/interventions/deliver").json() == {"items": []}
    assert client.get(
        "/api/v1/interventions", params={"case_id": "case", "status": "sent"}
    ).json() == {"items": [sent]}
    assert client.get("/api/v1/interventions", params={"case_id": "other"}).json() == {"items": []}


@pytest.mark.parametrize(
    "params",
    [
        pytest.param({"status": "failed"}, id="unknown-status"),
        pytest.param({"case_id": ""}, id="empty-case"),
    ],
)
def test_invalid_query_is_rejected(*, client, params):
    response = client.get("/api/v1/interventions", params=params)

    assert response.status_code == 422


def test_delivery_storage_error_returns_safe_message_and_stays_pending(
    *, client, observation_data, received_at
):
    _create_intervention(client=client, observation_data=observation_data, received_at=received_at)
    with client.app.state.engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE TRIGGER fail_delivery BEFORE UPDATE ON intervention
            BEGIN SELECT RAISE(ABORT, 'private database details'); END
        """)

    response = client.post("/api/v1/interventions/deliver")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "STORAGE_UNAVAILABLE",
            "message": "The interventions could not be delivered",
            "request_id": response.headers["X-Request-ID"],
        }
    }
    items = client.get("/api/v1/interventions").json()["items"]
    assert [item["status"] for item in items] == ["pending"]
