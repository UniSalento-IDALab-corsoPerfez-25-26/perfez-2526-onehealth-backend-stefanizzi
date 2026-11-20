import pandas as pd
import pytest
from fastapi.testclient import TestClient

from services.ai.app.main import app
from services.ai.app.routes import ai_service
from services.ai.app.scenarios import ENVIRONMENTAL_COLUMNS, SnapshotRepository

def test_scenarios_match_archived_ranking_and_keep_default_weights():
    client = TestClient(app)
    params = {"indicator_code": "BPCO", "year": 2023}
    response = client.get("/v1/dss/scenarios", params=params)
    assert response.status_code == 200
    data = response.json()
    assert data["health_basis"] == "crude_rate"
    scenarios = data["scenarios"]
    assert [scenarios[key][0]["asl"] for key in ("25", "50", "75")] == ["Taranto", "Brindisi", "Brindisi"]
    taranto = [next(row for row in scenarios[key] if row["asl"] == "Taranto") for key in ("25", "50", "75")]
    assert [row["rank"] for row in taranto] == [1, 2, 3]
    assert [row["score"] for row in taranto] == [88.54, 77.08, 65.62]
    legacy = client.get("/v1/ranking", params=params).json()
    assert result_pairs(scenarios["50"], "score") == result_pairs(legacy["items"], "priority_score")
    assert legacy["environment_weight"] == 0.5
    assert taranto[1]["standardized_rate"] is not None
    assert taranto[1]["health_points"] + taranto[1]["environment_points"] == pytest.approx(77.08, abs=0.01)
    assert data["coverage"]["Taranto"]["no2_mean_value"] == pytest.approx(94.4458)

def result_pairs(rows, field):
    return [(row["asl"], row[field]) for row in rows]


def test_missing_environment_has_no_score_or_position(monkeypatch):
    frame = ai_service.analytics_service.repository.load()
    affected = frame["asl"].eq("Taranto") & frame["year"].eq(2023)
    frame.loc[affected, ENVIRONMENTAL_COLUMNS] = float("nan")
    # Also test incomplete age information independently of the environmental gap.
    affected_age = frame["asl"].eq("Bari") & frame["age_group"].eq("85+") & frame["year"].eq(2023)
    frame = frame.loc[~affected_age]
    monkeypatch.setattr(ai_service.analytics_service, "repository", SnapshotRepository(frame))
    c = TestClient(app)
    response = c.get("/v1/dss/scenarios", params={"indicator_code": "BPCO", "year": 2023})
    assert response.status_code == 200
    for scenario in response.json()["scenarios"].values():
        taranto = next(row for row in scenario if row["asl"] == "Taranto")
        assert taranto["rank"] is None and taranto["score"] is None
        assert taranto["available_pollutants"] == 0
        assert all(pd.isna(value) for value in taranto["pollutants"].values())
        assert next(row for row in scenario if row["asl"] == "Bari")["standardized_rate"] is None
    assert c.get("/v1/dss/scenarios", params={"indicator_code": "BPCO", "year": 2099}).json()["status"] == "NO_DATA"
