from datetime import UTC
from datetime import datetime


def test_http_configuration_ingestion_and_restart_preserve_case_targets(open_client):
    now = datetime(2026, 10, 24, tzinfo=UTC)
    with open_client(now=lambda: now) as client:
        assert client.get("/api/v1/cases/missing").status_code == 404
        assert (
            client.put("/api/v1/cases/live/target", json={"target_speaker_order": 3}).status_code
            == 422
        )
        configured = client.put("/api/v1/cases/live/target", json={"target_speaker_order": 2})
        assert configured.status_code == 200
        assert configured.json()["target_speaker_id"] is None
        assert configured.json()["target_speaker_order"] == 2
        for index, label in enumerate(["PENDING", "A", "A", "B"]):
            response = client.post(
                "/api/v1/observations",
                json={
                    "case_id": "live",
                    "observation_id": f"word-{index}",
                    "speaker_id": label,
                    "start_at": f"2026-10-24T00:00:0{index}Z",
                    "end_at": f"2026-10-24T00:00:0{index + 1}Z",
                    "transcript": "Hello",
                    "signal_level_min": -50,
                    "signal_level_avg": -30,
                    "signal_level_max": -10,
                },
            )
            assert response.status_code == 201
        resolved = client.get("/api/v1/cases/live").json()
        assert resolved["target_speaker_id"] == "B"
        assert resolved["target_revision"] == 1
        manual = client.put("/api/v1/cases/live/target", json={"target_speaker_id": "A"}).json()
        assert manual["target_revision"] == 2
        assert (
            client.put("/api/v1/cases/replay/target", json={"target_speaker_id": "Q"}).status_code
            == 200
        )

    with open_client(now=lambda: now) as client:
        assert client.get("/api/v1/cases/live").json() == manual
        assert client.get("/api/v1/cases/replay").json()["target_speaker_id"] == "Q"
        # Earlier speech changes the order to B, A; manual selection remains A.
        response = client.post(
            "/api/v1/observations",
            json={
                "case_id": "live",
                "observation_id": "late-final",
                "speaker_id": "B",
                "start_at": "2026-10-23T23:59:58Z",
                "end_at": "2026-10-23T23:59:59Z",
                "transcript": "Earlier speech",
                "signal_level_min": -50,
                "signal_level_avg": -30,
                "signal_level_max": -10,
            },
        )
        assert response.status_code == 201
        assert client.get("/api/v1/cases/live").json() == manual
        automatic = client.put("/api/v1/cases/live/target", json={"target_speaker_order": 1}).json()
        assert automatic["target_speaker_id"] == "B"
        assert automatic["target_revision"] == 3
