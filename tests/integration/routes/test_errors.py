from datetime import UTC
from datetime import datetime


def test_invalid_body_uses_the_framework_detail_and_repeats_the_submitted_value(*, open_client):
    received_at = datetime(2026, 9, 26, 9, 2, 3, 456_789, tzinfo=UTC)
    with open_client(now=lambda: received_at) as client:
        observation_data = {
            "case_id": "case",
            "observation_id": "chunk",
            "speaker_id": "subject",
            "start_at": "2026-09-26T12:00:00.123456+03:00",
            "end_at": "2026-09-26T12:00:01.654321+03:00",
            "signal_level_min": -50.0,
            "signal_level_avg": -30.0,
            "signal_level_max": -10.0,
        }

        response = client.post("/api/v1/observations", json=observation_data)

    # Documented in docs/api.md: validation errors do not use the domain envelope.
    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {
                "type": "missing",
                "loc": ["body", "transcript"],
                "msg": "Field required",
                "input": observation_data,
            }
        ]
    }
    assert response.headers["X-Request-ID"]
    assert response.headers["Cache-Control"] == "no-store"
