from fastapi.testclient import TestClient

from services.health.app.main import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200

    payload = response.json()

    assert payload["service"] == "health-service"
    assert payload["status"] == "UP"
    assert payload["version"] == "1.0.0"


def test_indicators_endpoint():
    response = client.get("/v1/indicators")

    assert response.status_code == 200

    payload = response.json()

    assert payload["count"] == 4

    assert set(payload["items"]) == {
        "BPCO",
        "DIABETES",
        "HEART_FAILURE",
        "HYPERTENSION",
    }


def test_summary_endpoint():
    response = client.get("/v1/summary")

    assert response.status_code == 200

    payload = response.json()

    assert payload["record_count"] == 3000

    assert payload["years"] == [
        2020,
        2021,
        2022,
        2023,
    ]

    assert set(payload["indicators"]) == {
        "BPCO",
        "DIABETES",
        "HEART_FAILURE",
        "HYPERTENSION",
    }

    assert set(payload["sexes"]) == {
        "ALL",
        "F",
        "M",
    }


def test_quality_endpoint():
    response = client.get("/v1/quality")

    assert response.status_code == 200

    payload = response.json()

    assert payload["record_count"] == 3000

    assert payload["quality_status"] == {
        "VALID": 3000
    }

    assert payload["logical_duplicates"] == 0


def test_cases_filter():
    response = client.get(
        "/v1/cases",
        params={
            "indicator_code": "BPCO",
            "year": 2023,
            "asl": "Lecce",
            "sex": "F",
            "age_group": "65-69",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["count"] == 1

    item = payload["items"][0]

    assert item["indicator_code"] == "BPCO"
    assert item["year"] == 2023
    assert item["geographic_level"] == "ASL"
    assert item["geographic_area"] == "Lecce"
    assert item["sex"] == "F"
    assert item["age_group"] == "65-69"
    assert item["quality_status"] == "VALID"


def test_unknown_indicator_returns_empty_result():
    response = client.get(
        "/v1/cases",
        params={
            "indicator_code": "NOT_EXISTING",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["count"] == 0
    assert payload["items"] == []


def test_ingestion_endpoint():
    response = client.post(
        "/v1/ingestion/run"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "OK"

    assert (
        payload["dataset_path"]
        == (
            "data/processed/health/"
            "health_indicators_2020_2023.parquet"
        )
    )

    assert payload["record_count"] == 3000

    assert payload["years"] == [
        2020,
        2021,
        2022,
        2023,
    ]

    assert set(payload["indicators"]) == {
        "BPCO",
        "DIABETES",
        "HEART_FAILURE",
        "HYPERTENSION",
    }

    assert payload["quality_status"] == {
        "VALID": 3000
    }

    assert payload["logical_duplicates"] == 0