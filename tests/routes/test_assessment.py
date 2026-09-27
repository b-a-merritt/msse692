from datetime import timedelta
from uuid import uuid4

import pytest

from normative_conformance.services.assessment.check_repairs import check_repairs
from normative_conformance.services.assessment.evaluate_case import evaluate_case


def _create_pending(*, client, observation_data, case_id="case"):
    response = client.post(
        "/api/v1/observations",
        json=observation_data
        | {
            "case_id": case_id,
            "speaker_id": client.app.state.settings.subject_speaker_id,
            "start_at": "2026-09-26T09:00:00Z",
            "end_at": "2026-09-26T09:00:31Z",
        },
    )
    assert response.status_code == 202
    rows = evaluate_case(
        case_id=case_id,
        evaluation_id=uuid4(),
        engine=client.app.state.engine,
        scheduler=client.app.state.scheduler,
        now=client.app.state.clock,
    )
    assert len(rows) == 1
    return rows[0]


def test_returns_api_records_with_original_extents_and_resolution_links(
    *, client, observation_data, received_at
):
    pending = _create_pending(client=client, observation_data=observation_data)
    _create_pending(client=client, observation_data=observation_data, case_id="other")
    # A later arrival must not change the pending assessment's captured extent.
    assert (
        client.post(
            "/api/v1/observations", json=observation_data | {"observation_id": "later"}
        ).status_code
        == 202
    )

    response = client.get("/api/v1/cases/case/assessments")

    assert response.status_code == 200
    due_at = (received_at + timedelta(seconds=10)).isoformat().replace("+00:00", "Z")
    expected_pending = {
        "assessment_id": pending.assessment_id,
        "resolves_assessment_id": None,
        "evaluation_id": pending.evaluation_id,
        "case_id": "case",
        "subject_speaker_id": client.app.state.settings.subject_speaker_id,
        "model_id": "extended_turn",
        "model_version": "1",
        "evaluated_at": received_at.isoformat().replace("+00:00", "Z"),
        "status": "pending",
        "extent": {
            "through_sequence": 1,
            "observation_count": 1,
            "observation_ids": ["chunk"],
        },
        "explanation": {
            "reason_code": "awaiting_repair",
            "summary": "Awaiting repair",
            "rules": [
                {
                    "rule_id": "long_turn",
                    "outcome": "pending",
                    "reason": "Awaiting repair",
                    "observation_ids": [],
                    "deadline_at": due_at,
                }
            ],
        },
        "next_due_at": due_at,
    }
    assert response.json() == {"items": [expected_pending]}

    resolution = check_repairs(
        case_id="case",
        evaluation_id=uuid4(),
        engine=client.app.state.engine,
        scheduler=client.app.state.scheduler,
        now=lambda: received_at + timedelta(seconds=10),
    )[0]
    response = client.get("/api/v1/cases/case/assessments")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            expected_pending,
            expected_pending
            | {
                "assessment_id": resolution.assessment_id,
                "resolves_assessment_id": pending.assessment_id,
                "evaluation_id": resolution.evaluation_id,
                "evaluated_at": due_at,
                "status": "conformant",
                "extent": {
                    "through_sequence": 2,
                    "observation_count": 2,
                    "observation_ids": ["chunk", "later"],
                },
                "explanation": {
                    "reason_code": "matched",
                    "summary": "The model matched",
                    "rules": [
                        {
                            "rule_id": "long_turn",
                            "outcome": "satisfied",
                            "reason": "The model matched",
                            "observation_ids": [],
                            "deadline_at": None,
                        }
                    ],
                },
                "next_due_at": None,
            },
        ]
    }


def test_preserves_repair_evidence_in_the_explanation(*, client, observation_data, received_at):
    pending = _create_pending(client=client, observation_data=observation_data)
    assert (
        client.post(
            "/api/v1/observations",
            json=observation_data
            | {
                "observation_id": "apology",
                "speaker_id": client.app.state.settings.subject_speaker_id,
                "start_at": "2026-09-26T09:00:32Z",
                "end_at": "2026-09-26T09:00:33Z",
                "transcript": "I apologize",
            },
        ).status_code
        == 202
    )
    check_repairs(
        case_id="case",
        evaluation_id=uuid4(),
        engine=client.app.state.engine,
        scheduler=client.app.state.scheduler,
        now=lambda: received_at + timedelta(seconds=5),
    )

    response = client.get("/api/v1/cases/case/assessments")

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["model_id"] for item in items] == ["extended_turn", "apology", "extended_turn"]
    resolution = items[-1]
    assert resolution["status"] == "non-conformant"
    assert resolution["resolves_assessment_id"] == pending.assessment_id
    assert resolution["explanation"]["reason_code"] == "repaired"
    assert resolution["explanation"]["rules"][0]["observation_ids"] == ["apology"]
    assert resolution["extent"]["observation_ids"] == ["chunk", "apology"]


@pytest.mark.parametrize("case_id", ["case", "missing"])
def test_returns_empty_items_when_no_assessments_exist(*, client, observation_data, case_id):
    assert client.post("/api/v1/observations", json=observation_data).status_code == 202

    response = client.get(f"/api/v1/cases/{case_id}/assessments")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_openapi_describes_the_assessment_response(*, client):
    responses = client.get("/openapi.json").json()["paths"]["/api/v1/cases/{case_id}/assessments"][
        "get"
    ]["responses"]
    assert responses["200"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/ListResponse_Assessment_"
    )
