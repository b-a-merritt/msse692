from datetime import UTC
from datetime import datetime

import pytest

from normative_conformance import models
from normative_conformance.database import write_session
from normative_conformance.timestamps import to_microseconds


def _timestamp(value):
    return value.isoformat().replace("+00:00", "Z")


def test_delivery_marks_listed_interventions_sent_once(*, open_client):
    received_at = datetime(2026, 9, 26, 9, 2, 3, 456_789, tzinfo=UTC)
    with open_client(now=lambda: received_at) as client:
        with write_session(engine=client.app.state.engine) as session:
            session.add(models.ConversationCase(case_id="case", created_at_us=0))
            session.flush()
            session.add(
                models.TargetAssignment(
                    case_id="case", target_revision=1, assigned_at_us=0, speaker_id="A"
                )
            )
            session.add(
                models.Observation(
                    case_id="case",
                    observation_id="chunk",
                    sequence=1,
                    speaker_id="A",
                    start_at_us=0,
                    end_at_us=1_000_000,
                    received_at_us=0,
                    transcript="hello",
                    signal_level_min=-60.0,
                    signal_level_avg=-30.0,
                    signal_level_max=0.0,
                )
            )
            session.flush()
            assessment = models.Assessment(
                case_id="case",
                target_revision=1,
                model_id="jev-1.14.0",
                prompt_version="conversation-1",
                evaluated_at_us=1,
                completed_at_us=2,
                after_sequence=0,
                through_sequence=1,
                action="intervene",
                action_confidence=0.9,
                selection_threshold=0.7,
                request_json="{}",
            )
            session.add(assessment)
            session.flush()
            intervention = models.Intervention(
                assessment_id=assessment.assessment_id,
                message="Feedback",
                created_at_us=to_microseconds(value=received_at),
            )
            session.add(intervention)
            session.commit()
        pending = {
            "intervention_id": intervention.intervention_id,
            "case_id": "case",
            "target_speaker_id": "A",
            "assessment_id": assessment.assessment_id,
            "message": "Feedback",
            "created_at": _timestamp(received_at),
            "status": "pending",
            "sent_at": None,
        }
        sent = pending | {"status": "sent", "sent_at": _timestamp(received_at)}

        assert client.get("/api/v1/interventions").json() == {"items": [pending]}
        assert client.get("/api/v1/interventions", params={"status": "sent"}).json() == {
            "items": []
        }

        response = client.post("/api/v1/cases/case/interventions/deliver")

        assert response.status_code == 200
        assert response.json() == {"items": [sent]}
        assert client.post("/api/v1/cases/case/interventions/deliver").json() == {"items": []}
        assert client.get(
            "/api/v1/interventions", params={"case_id": "case", "status": "sent"}
        ).json() == {"items": [sent]}


@pytest.mark.parametrize(
    "params",
    [
        pytest.param({"status": "failed"}, id="unknown-status"),
        pytest.param({"case_id": ""}, id="empty-case"),
    ],
)
def test_invalid_query_is_rejected(*, open_client, params):
    received_at = datetime(2026, 9, 26, 9, 2, 3, 456_789, tzinfo=UTC)
    with open_client(now=lambda: received_at) as client:
        response = client.get("/api/v1/interventions", params=params)

        assert response.status_code == 422


def test_delivery_storage_error_returns_safe_message_and_stays_pending(*, open_client):
    received_at = datetime(2026, 9, 26, 9, 2, 3, 456_789, tzinfo=UTC)
    with open_client(now=lambda: received_at) as client:
        with write_session(engine=client.app.state.engine) as session:
            session.add(models.ConversationCase(case_id="case", created_at_us=0))
            session.flush()
            session.add(
                models.TargetAssignment(
                    case_id="case", target_revision=1, assigned_at_us=0, speaker_id="A"
                )
            )
            session.add(
                models.Observation(
                    case_id="case",
                    observation_id="chunk",
                    sequence=1,
                    speaker_id="A",
                    start_at_us=0,
                    end_at_us=1_000_000,
                    received_at_us=0,
                    transcript="hello",
                    signal_level_min=-60.0,
                    signal_level_avg=-30.0,
                    signal_level_max=0.0,
                )
            )
            session.flush()
            assessment = models.Assessment(
                case_id="case",
                target_revision=1,
                model_id="jev-1.14.0",
                prompt_version="conversation-1",
                evaluated_at_us=1,
                completed_at_us=2,
                after_sequence=0,
                through_sequence=1,
                action="intervene",
                action_confidence=0.9,
                selection_threshold=0.7,
                request_json="{}",
            )
            session.add(assessment)
            session.flush()
            intervention = models.Intervention(
                assessment_id=assessment.assessment_id,
                message="Feedback",
                created_at_us=to_microseconds(value=received_at),
            )
            session.add(intervention)
            session.commit()
        with client.app.state.engine.begin() as connection:
            connection.exec_driver_sql("""
                CREATE TRIGGER fail_delivery BEFORE UPDATE ON intervention
                BEGIN SELECT RAISE(ABORT, 'private database details'); END
            """)

        response = client.post("/api/v1/cases/case/interventions/deliver")

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
