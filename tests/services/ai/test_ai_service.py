from fastapi.testclient import TestClient

from services.ai.app.main import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200

    assert response.json() == {
        "service": "ai-service",
        "status": "UP",
        "version": "1.0.0",
    }


def test_model_card():
    response = client.get(
        "/v1/model-card"
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["model"]
        == "EXPLAINABLE_ONE_HEALTH_PRIORITY"
    )

    assert data["version"] == "1.0.0"

    assert (
        data["type"]
        == "EXPLAINABLE_RULE_BASED_SCORING"
    )

    assert (
        data["unit_of_analysis"]
        == "ASL_YEAR_INDICATOR"
    )

    assert data["weights"] == {
        "health": 0.5,
        "environment": 0.5,
    }

    assert (
        "Missing environmental"
        in data["missing_data_policy"]
    )

    assert (
        data["priority_levels"]["UNDEFINED"]
        == "priority score cannot be calculated"
    )


def test_bpco_2023_ranking():
    response = client.get(
        "/v1/ranking",
        params={
            "indicator_code": "BPCO",
            "year": 2023,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "OK"
    assert data["count"] == 6

    assert data["health_weight"] == 0.5
    assert data["environment_weight"] == 0.5

    assert [
        item["asl"]
        for item in data["items"]
    ] == [
        "Brindisi",
        "Taranto",
        "Bari",
        "BAT",
        "Lecce",
        "Foggia",
    ]

    assert [
        item["priority_score"]
        for item in data["items"]
    ] == [
        81.25,
        77.08,
        64.58,
        62.50,
        45.83,
        18.75,
    ]


def test_priority_levels():
    response = client.get(
        "/v1/ranking",
        params={
            "indicator_code": "BPCO",
            "year": 2023,
        },
    )

    assert response.status_code == 200

    items = response.json()["items"]

    assert [
        item["priority_level"]
        for item in items
    ] == [
        "HIGH",
        "HIGH",
        "MEDIUM",
        "MEDIUM",
        "LOW",
        "LOW",
    ]


def test_lecce_priority():
    response = client.get(
        "/v1/priority",
        params={
            "indicator_code": "BPCO",
            "year": 2023,
            "asl": "Lecce",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "OK"

    assert data["indicator_code"] == "BPCO"
    assert data["year"] == 2023
    assert data["asl"] == "Lecce"

    assert data["priority_rank"] == 5
    assert data["priority_level"] == "LOW"
    assert data["priority_score"] == 45.83

    assert data["cases"] == 31688
    assert data["population"] == 482772

    assert (
        data["prevalence_per_1000"]
        == 65.6376
    )

    assert (
        data["health_percentile"]
        == 0.3333
    )

    assert (
        data["environment_percentile"]
        == 0.5833
    )

    assert (
        data["integration_quality_status"]
        == "VALID"
    )

    assert (
        data["meteo_quality_status"]
        == "VALID"
    )

    assert data["meteo_available"] is True

    assert (
        data["meteo_year_coverage_percent"]
        == 100.0
    )


def test_lecce_explanation():
    response = client.get(
        "/v1/explain",
        params={
            "indicator_code": "BPCO",
            "year": 2023,
            "asl": "Lecce",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "OK"

    assert data["priority_rank"] == 5
    assert data["priority_level"] == "LOW"
    assert data["priority_score"] == 45.83

    health = data[
        "health_component"
    ]

    assert (
        health["prevalence_per_1000"]
        == 65.6376
    )

    assert (
        health["relative_percentile"]
        == 0.3333
    )

    assert health["weight"] == 0.5

    environment = data[
        "environment_component"
    ]

    assert (
        environment["relative_percentile"]
        == 0.5833
    )

    assert environment["weight"] == 0.5

    pollutants = {
        item["variable"]: item
        for item
        in environment["variables"]
    }

    assert (
        pollutants[
            "no2_mean_value"
        ]["value"]
        == 25.8291
    )

    assert (
        pollutants[
            "no2_mean_value"
        ]["relative_percentile"]
        == 0.1667
    )

    assert (
        pollutants[
            "o3_mean_value"
        ]["value"]
        == 88.8756
    )

    assert (
        pollutants[
            "o3_mean_value"
        ]["relative_percentile"]
        == 0.5
    )

    assert (
        pollutants[
            "pm10_mean_value"
        ]["value"]
        == 22.3395
    )

    assert (
        pollutants[
            "pm10_mean_value"
        ]["relative_percentile"]
        == 0.6667
    )

    assert (
        pollutants[
            "pm2_5_mean_value"
        ]["value"]
        == 12.9094
    )

    assert (
        pollutants[
            "pm2_5_mean_value"
        ]["relative_percentile"]
        == 1.0
    )

    quality = data["data_quality"]

    assert (
        quality[
            "integration_quality_status"
        ]
        == "VALID"
    )

    assert (
        quality[
            "meteo_quality_status"
        ]
        == "VALID"
    )

    assert (
        quality["meteo_available"]
        is True
    )

    assert (
        quality[
            "meteo_year_coverage_percent"
        ]
        == 100.0
    )


def test_bat_missing_meteorology_is_preserved():
    response = client.get(
        "/v1/priority",
        params={
            "indicator_code": "BPCO",
            "year": 2023,
            "asl": "BAT",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "OK"

    assert data["priority_rank"] == 4
    assert data["priority_level"] == "MEDIUM"
    assert data["priority_score"] == 62.5

    assert (
        data["integration_quality_status"]
        == "VALID_WITHOUT_METEO"
    )

    assert (
        data["meteo_quality_status"]
        is None
    )

    assert (
        data["meteo_available"]
        is False
    )

    assert (
        data[
            "meteo_year_coverage_percent"
        ]
        is None
    )


def test_unknown_indicator_ranking():
    response = client.get(
        "/v1/ranking",
        params={
            "indicator_code":
                "UNKNOWN_INDICATOR",
            "year": 2023,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "NO_DATA"
    assert data["items"] == []
    assert data["count"] == 0


def test_unknown_asl_priority():
    response = client.get(
        "/v1/priority",
        params={
            "indicator_code": "BPCO",
            "year": 2023,
            "asl": "UNKNOWN_ASL",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "NO_DATA"
    assert data["asl"] == "UNKNOWN_ASL"


def test_unknown_asl_explanation():
    response = client.get(
        "/v1/explain",
        params={
            "indicator_code": "BPCO",
            "year": 2023,
            "asl": "UNKNOWN_ASL",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "NO_DATA"
    assert data["asl"] == "UNKNOWN_ASL"