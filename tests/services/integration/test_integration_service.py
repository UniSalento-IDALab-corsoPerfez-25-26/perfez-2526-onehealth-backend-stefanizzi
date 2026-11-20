from fastapi.testclient import TestClient

from services.integration.app.main import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200

    payload = response.json()

    assert payload["service"] == "integration-service"
    assert payload["status"] == "UP"
    assert payload["version"] == "1.0.0"


def test_summary_endpoint():
    response = client.get("/v1/summary")

    assert response.status_code == 200

    payload = response.json()

    assert payload["record_count"] == 2160

    assert payload["years"] == [
        2021,
        2022,
        2023,
    ]

    assert set(payload["areas"]) == {
        "BAT",
        "Bari",
        "Brindisi",
        "Foggia",
        "Lecce",
        "Taranto",
    }

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

    assert payload["record_count"] == 2160
    assert payload["logical_duplicates"] == 0

    assert payload[
        "integration_quality_status"
    ] == {
        "VALID_WITHOUT_METEO": 1560,
        "VALID_WITH_PARTIAL_METEO": 480,
        "VALID": 120,
    }


def test_master_filter():
    response = client.get(
        "/v1/master",
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
    assert item["asl"] == "Lecce"
    assert item["sex"] == "F"
    assert item["age_group"] == "65-69"

    assert item["cases"] == 1645
    assert item["population"] == 26427
    assert item["prevalence_per_1000"] == 62.2469

    assert item["pm10_mean_value"] == 22.3395
    assert item["pm2_5_mean_value"] == 12.9094
    assert item["no2_mean_value"] == 25.8291
    assert item["o3_mean_value"] == 88.8756

    assert item["meteo_available"] is True
    assert item["meteo_is_full_year"] is True
    assert item["meteo_quality_status"] == "VALID"

    assert (
        item["integration_quality_status"]
        == "VALID"
    )


def test_unknown_filter_returns_empty():
    response = client.get(
        "/v1/master",
        params={
            "asl": "NOT_EXISTING",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["count"] == 0
    assert payload["items"] == []


def test_ingestion_endpoint():
    response = client.post(
        "/v1/ingestion/run",
        params={
            "start_year": 2021,
            "end_year": 2023,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "OK"

    assert payload["record_count"] == 2160

    assert payload["years"] == [
        2021,
        2022,
        2023,
    ]

    assert payload[
        "records_with_meteorology"
    ] == 600

    assert payload[
        "records_without_meteorology"
    ] == 1560

    assert payload[
        "integration_quality_status"
    ] == {
        "VALID_WITHOUT_METEO": 1560,
        "VALID_WITH_PARTIAL_METEO": 480,
        "VALID": 120,
    }

    assert payload["logical_duplicates"] == 0