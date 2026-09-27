import pytest


def test_catalog_exposes_repair_allowances(*, client):
    response = client.get("/api/v1/models")

    assert response.status_code == 200
    items = response.json()["items"]
    assert {item["model_id"]: item["repair_allowance_us"] for item in items} == {
        "apology": None,
        "extended_turn": 10_000_000,
        "high_intensity_address": 10_000_000,
        "repeated_interruption": 10_000_000,
    }
    assert all("repairable" not in item for item in items)


@pytest.mark.parametrize("model_id,allowance", [("extended_turn", 10_000_000), ("apology", None)])
def test_model_version_exposes_its_repair_allowance(*, client, model_id, allowance):
    response = client.get(f"/api/v1/models/{model_id}/versions/1")

    assert response.status_code == 200
    assert response.json()["repair_allowance_us"] == allowance
    assert "repairable" not in response.json()
