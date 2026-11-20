"""Compare the same archived cohort under three explicit DSS weight scenarios."""

import pandas as pd

from services.ai.app.service import AIService, ENVIRONMENTAL_COLUMNS
from services.analytics.app.repository import AnalyticsRepository
from services.analytics.app.service import AnalyticsService

WEIGHTS = (25, 50, 75)
REFERENCE_YEAR = 2023
REFERENCE_INDICATOR = "BPCO"
AGE_GROUPS = ("40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79", "80-84", "85+")


class SnapshotRepository:
    """Use one dataset snapshot for all scenarios of the request."""

    def __init__(self, frame: pd.DataFrame):
        self.frame = frame

    def load(self) -> pd.DataFrame:
        return self.frame


def get_options(repository: AnalyticsRepository) -> dict:
    frame = repository.load().loc[lambda rows: rows["sex"].eq("ALL")]
    return {
        "indicators": [
            {"code": str(code), "label": str(group["indicator_name"].iloc[0]),
             "years": sorted(int(year) for year in group["year"].dropna().unique())}
            for code, group in frame.groupby("indicator_code")
        ]
    }


def health_rates(frame: pd.DataFrame, indicator_code: str, year: int) -> dict:
    totals = frame.loc[frame["sex"].eq("ALL") & frame["age_group"].isin(AGE_GROUPS)]
    reference = totals.loc[totals["indicator_code"].eq(REFERENCE_INDICATOR) & totals["year"].eq(REFERENCE_YEAR)]
    if (
        reference["asl"].nunique() != 6
        or reference.duplicated(["asl", "age_group"]).any()
        or not reference.groupby("asl")["age_group"].nunique().eq(len(AGE_GROUPS)).all()
        or not reference["population"].gt(0).all()
    ):
        return {}
    population = reference.groupby("age_group")["population"].sum()
    weights = population / population.sum()
    selected = totals.loc[totals["indicator_code"].eq(indicator_code) & totals["year"].eq(year)]
    standardized = {}
    for asl, group in selected.groupby("asl"):
        indexed = group.set_index("age_group")
        if not indexed.index.is_unique or set(indexed.index) != set(AGE_GROUPS):
            continue
        if not indexed["population"].gt(0).all() or not indexed["cases"].ge(0).all():
            continue
        rates = 1000 * indexed["cases"] / indexed["population"]
        standardized[asl] = round(float((rates * weights).sum()), 4)
    return standardized


def compare_scenarios(repository: AnalyticsRepository, indicator_code: str, year: int) -> dict:
    frame = repository.load()
    analytics = AnalyticsService(SnapshotRepository(frame))
    standardized = health_rates(frame, indicator_code, year)
    scenarios = {}
    for percent in WEIGHTS:
        service = AIService(analytics, environment_weight=percent / 100)
        dataset = service.build_priority_dataset(indicator_code=indicator_code, year=year)
        records = []
        for _, record in dataset.iterrows():
            item = {
                "asl": record["asl"],
                "rank": record["priority_rank"],
                "score": record["priority_score"],
                "cases": record["cases"],
                "population": record["population"],
                "crude_rate": record["prevalence_per_1000"],
                "standardized_rate": standardized.get(record["asl"]),
                "health_points": round(float(record["health_percentile"] * service.HEALTH_WEIGHT * 100), 4),
                "environment_points": round(float(record["environment_percentile"] * service.ENVIRONMENT_WEIGHT * 100), 4),
                "integration_quality_status": record.get("integration_quality_status"),
                "available_pollutants": sum(pd.notna(record.get(key)) for key in ENVIRONMENTAL_COLUMNS),
                "pollutants": {
                    key: record.get(key) for key in ENVIRONMENTAL_COLUMNS
                },
            }
            records.append(item)
        if records:
            rows = pd.DataFrame(records)
            for item in records:
                item["pollutants"] = {
                    key: None if pd.isna(value) else float(value)
                    for key, value in item["pollutants"].items()
                }
            rows["pollutants"] = [item["pollutants"] for item in records]
            records = service._json_safe(rows)
        scenarios[str(percent)] = records

    # The archived availability measures refer to ASL and year, not age strata.
    selected = frame.loc[frame["indicator_code"].eq(indicator_code) & frame["year"].eq(year)]
    coverage = {}
    weather = {}
    for asl, group in selected.groupby("asl"):
        coverage[asl] = {}
        weather[asl] = {}
        for key in ("meteo_available", "meteo_is_full_year", "meteo_year_coverage_percent"):
            values = group[key].dropna().unique() if key in group else []
            if len(values) == 1:
                weather[asl][key] = float(values[0]) if key.endswith("_percent") else bool(values[0])
            else:
                weather[asl][key] = None
        for key in ENVIRONMENTAL_COLUMNS:
            column = key.replace("_mean_value", "_availability_percent")
            values = group[column].dropna().unique() if column in group else []
            coverage[asl][key] = float(values[0]) if len(values) == 1 else None

    return {
        "status": "OK" if scenarios["50"] else "NO_DATA",
        "indicator_code": indicator_code,
        "year": year,
        "health_basis": "crude_rate",
        "reference_year": REFERENCE_YEAR,
        "age_minimum": 40,
        "scenarios": scenarios,
        "coverage": coverage,
        "weather": weather,
    }
