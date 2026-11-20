from fastapi.testclient import TestClient

from services.demography.app.main import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200

    payload = response.json()

    assert payload["service"] == "demography-service"
    assert payload["status"] == "UP"
    assert payload["version"] == "1.0.0"


def test_summary_endpoint():
    response = client.get("/v1/summary")

    assert response.status_code == 200

    payload = response.json()

    assert payload["record_count"] == 720

    assert payload["years"] == [
        2020,
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

    assert set(payload["sexes"]) == {
        "ALL",
        "F",
        "M",
    }


def test_quality_endpoint():
    response = client.get("/v1/quality")

    assert response.status_code == 200

    payload = response.json()

    assert payload["record_count"] == 720

    assert payload["quality_status"] == {
        "VALID": 720
    }

    assert payload["logical_duplicates"] == 0


def test_population_filter():
    response = client.get(
        "/v1/population",
        params={
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

    assert item["year"] == 2023
    assert item["asl"] == "Lecce"
    assert item["sex"] == "F"
    assert item["age_group"] == "65-69"
    assert item["population"] == 26427
    assert item["source"] == "ISTAT"
    assert item["quality_status"] == "VALID"


def test_unknown_area_returns_empty_result():
    response = client.get(
        "/v1/population",
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
        "/v1/ingestion/run"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "OK"

    assert (
        payload["detail_dataset_path"]
        == (
            "data/processed/demography/"
            "population_puglia_2020_2023.parquet"
        )
    )

    assert (
        payload["asl_dataset_path"]
        == (
            "data/processed/demography/"
            "population_asl_2020_2023.parquet"
        )
    )

    assert payload["record_count"] == 720

    assert payload["years"] == [
        2020,
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

    assert payload["quality_status"] == {
        "VALID": 720
    }

    assert payload["logical_duplicates"] == 0