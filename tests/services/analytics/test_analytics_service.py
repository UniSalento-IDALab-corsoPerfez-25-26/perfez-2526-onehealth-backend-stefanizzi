from fastapi.testclient import TestClient

from services.analytics.app.main import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data == {
        "service": "analytics-service",
        "status": "UP",
        "version": "1.0.0",
    }


def test_summary_endpoint():
    response = client.get("/v1/summary")

    assert response.status_code == 200

    data = response.json()

    assert data["record_count"] == 2160

    assert data["years"] == [
        2021,
        2022,
        2023,
    ]

    assert data["areas"] == [
        "BAT",
        "Bari",
        "Brindisi",
        "Foggia",
        "Lecce",
        "Taranto",
    ]

    assert data["indicators"] == [
        "BPCO",
        "DIABETES",
        "HEART_FAILURE",
        "HYPERTENSION",
    ]

    assert data[
        "available_environmental_variables"
    ] == [
        "no2_mean_value",
        "o3_mean_value",
        "pm10_mean_value",
        "pm2_5_mean_value",
    ]


def test_kpi_bpco_lecce_2023():
    response = client.get(
        "/v1/kpi",
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
    assert data["sex"] == "ALL"

    assert data["cases"] == 31688
    assert data["population"] == 482772
    assert (
        data["prevalence_per_1000"]
        == 65.6376
    )


def test_kpi_unknown_indicator():
    response = client.get(
        "/v1/kpi",
        params={
            "indicator_code":
                "UNKNOWN_INDICATOR",
            "year": 2023,
            "asl": "Lecce",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "NO_DATA"
    assert (
        data["indicator_code"]
        == "UNKNOWN_INDICATOR"
    )
    assert data["year"] == 2023
    assert data["asl"] == "Lecce"


def test_trend_bpco_lecce():
    response = client.get(
        "/v1/trends",
        params={
            "indicator_code": "BPCO",
            "asl": "Lecce",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 3

    assert data["items"] == [
        {
            "year": 2021,
            "cases": 30864,
            "population": 478952,
            "prevalence_per_1000":
                64.4407,
        },
        {
            "year": 2022,
            "cases": 31333,
            "population": 482250,
            "prevalence_per_1000":
                64.9725,
        },
        {
            "year": 2023,
            "cases": 31688,
            "population": 482772,
            "prevalence_per_1000":
                65.6376,
        },
    ]


def test_territorial_ranking_bpco_2023():
    response = client.get(
        "/v1/territories",
        params={
            "indicator_code": "BPCO",
            "year": 2023,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 6

    items = data["items"]

    assert [
        item["asl"]
        for item in items
    ] == [
        "Taranto",
        "Brindisi",
        "Bari",
        "BAT",
        "Lecce",
        "Foggia",
    ]

    assert items[0] == {
        "rank": 1,
        "asl": "Taranto",
        "cases": 25520,
        "population": 342107,
        "prevalence_per_1000":
            74.5965,
    }

    assert items[-1] == {
        "rank": 6,
        "asl": "Foggia",
        "cases": 21731,
        "population": 349996,
        "prevalence_per_1000":
            62.0893,
    }


def test_correlations_bpco():
    response = client.get(
        "/v1/correlations",
        params={
            "indicator_code": "BPCO",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "OK"

    assert (
        data["indicator_code"]
        == "BPCO"
    )

    assert (
        data[
            "analytical_granularity"
        ]
        == "ASL_YEAR_INDICATOR"
    )

    assert data["observations"] == 18

    correlations = {
        item["variable"]:
            item["coefficient"]
        for item in data[
            "correlations"
        ]
    }

    assert correlations[
        "o3_mean_value"
    ] == 0.5403

    assert correlations[
        "pm2_5_mean_value"
    ] == -0.3547

    assert correlations[
        "pm10_mean_value"
    ] == 0.2119

    assert correlations[
        "no2_mean_value"
    ] == 0.205

    for item in data["correlations"]:
        assert (
            item["method"]
            == "pearson"
        )

        assert (
            item["observations"]
            == 18
        )

    assert (
        "must not be interpreted"
        in data["warning"]
    )


def test_correlations_unknown_indicator():
    response = client.get(
        "/v1/correlations",
        params={
            "indicator_code":
                "UNKNOWN_INDICATOR",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "NO_DATA"
    assert data["observations"] == 0
    assert data["correlations"] == []