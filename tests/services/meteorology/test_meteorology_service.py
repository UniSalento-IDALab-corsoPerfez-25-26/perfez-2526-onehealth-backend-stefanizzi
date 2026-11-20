from fastapi.testclient import TestClient

from services.meteorology.app.main import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200

    payload = response.json()

    assert payload["service"] == "meteorology-service"
    assert payload["status"] == "UP"
    assert payload["version"] == "1.0.0"


def test_summary_endpoint():
    response = client.get("/v1/summary")

    assert response.status_code == 200

    payload = response.json()

    assert payload["record_count"] == 5
    assert payload["years"] == [2023]

    assert set(payload["areas"]) == {
        "Bari",
        "Brindisi",
        "Foggia",
        "Lecce",
        "Taranto",
    }


def test_quality_endpoint():
    response = client.get("/v1/quality")

    assert response.status_code == 200

    payload = response.json()

    assert payload["record_count"] == 5

    assert payload["quality_status"] == {
        "PARTIAL_COVERAGE": 4,
        "VALID": 1,
    }

    assert payload["full_year_records"] == 1
    assert payload["partial_year_records"] == 4
    assert payload["logical_duplicates"] == 0


def test_lecce_full_coverage():
    response = client.get(
        "/v1/meteorology",
        params={
            "year": 2023,
            "asl": "Lecce",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["count"] == 1

    item = payload["items"][0]

    assert item["year"] == 2023
    assert item["asl"] == "Lecce"

    assert item["meteo_days_available"] == 365
    assert item["meteo_expected_days"] == 365
    assert item["meteo_year_coverage_percent"] == 100.0
    assert item["meteo_quality_status"] == "VALID"
    assert item["meteo_is_full_year"] is True


def test_bari_partial_coverage():
    response = client.get(
        "/v1/meteorology",
        params={
            "year": 2023,
            "asl": "Bari",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["count"] == 1

    item = payload["items"][0]

    assert item["year"] == 2023
    assert item["asl"] == "Bari"

    assert item["meteo_year_coverage_percent"] == 66.58
    assert item["meteo_quality_status"] == "PARTIAL_COVERAGE"
    assert item["meteo_is_full_year"] is False


def test_unknown_area_returns_empty_result():
    response = client.get(
        "/v1/meteorology",
        params={
            "asl": "BAT",
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
            "year": 2023,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "OK"
    assert payload["year"] == 2023

    assert payload["record_count"] == 5

    assert set(payload["areas"]) == {
        "Bari",
        "Brindisi",
        "Foggia",
        "Lecce",
        "Taranto",
    }

    assert payload["quality_status"] == {
        "PARTIAL_COVERAGE": 4,
        "VALID": 1,
    }

    assert payload["full_year_records"] == 1
    assert payload["partial_year_records"] == 4
    assert payload["logical_duplicates"] == 0