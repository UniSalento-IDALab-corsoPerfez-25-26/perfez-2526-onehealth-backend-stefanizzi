from fastapi.testclient import TestClient

from services.environment.app.main import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200

    payload = response.json()

    assert payload["service"] == "environment-service"
    assert payload["status"] == "UP"
    assert payload["version"] == "1.0.0"


def test_summary_endpoint():
    response = client.get("/v1/summary")

    assert response.status_code == 200

    payload = response.json()

    assert payload["record_count"] == 72

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

    assert set(payload["pollutants"]) == {
        "NO2",
        "O3",
        "PM10",
        "PM2.5",
    }


def test_quality_endpoint():
    response = client.get("/v1/quality")

    assert response.status_code == 200

    payload = response.json()

    assert payload["record_count"] == 72

    assert payload["quality_status"] == {
        "VALID": 72
    }

    assert payload["logical_duplicates"] == 0


def test_exposure_filter():
    response = client.get(
        "/v1/exposure",
        params={
            "year": 2021,
            "asl": "Lecce",
            "pollutant_code": "PM10",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["count"] == 1

    item = payload["items"][0]

    assert item["year"] == 2021
    assert item["asl"] == "Lecce"
    assert item["pollutant_code"] == "PM10"

    assert item["records"] == 2920
    assert item["valid_values"] == 2655
    assert item["stations"] == 8
    assert item["days"] == 365

    assert item["mean_value"] == 21.0169
    assert item["median_value"] == 18.0
    assert item["maximum_value"] == 102.0

    assert item["source"] == "ARPAP"
    assert item["quality_status"] == "VALID"


def test_unknown_pollutant_returns_empty_result():
    response = client.get(
        "/v1/exposure",
        params={
            "pollutant_code": "NOT_EXISTING",
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
        payload["long_dataset_path"]
        == (
            "data/processed/one_health/"
            "environmental_exposure_asl_2021_2023.parquet"
        )
    )

    assert (
        payload["wide_dataset_path"]
        == (
            "data/processed/one_health/"
            "environmental_exposure_asl_2021_2023_wide.parquet"
        )
    )

    assert payload["record_count"] == 72
    assert payload["wide_record_count"] == 18

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

    assert set(payload["pollutants"]) == {
        "NO2",
        "O3",
        "PM10",
        "PM2.5",
    }

    assert payload["quality_status"] == {
        "VALID": 72
    }

    assert payload["logical_duplicates"] == 0