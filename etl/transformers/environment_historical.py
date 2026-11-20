"""Historical ARPA Puglia Environment curated dataset (2010-2020).

Additive historical branch: frozen 2021-2023 outputs are never overwritten.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

CORE_POLLUTANTS = ("PM10", "NO2", "O3")
EXTENDED_POLLUTANTS = ("PM2.5",)
ASLS = ("BAT", "Bari", "Brindisi", "Foggia", "Lecce", "Taranto")

REQUIRED_COLUMNS = (
    "year","asl","pollutant","mean_value","station_count",
    "valid_observations","expected_observations","coverage","source","quality_status",
)

def quality_from_coverage(coverage: float) -> str:
    if coverage >= 0.90:
        return "VALID"
    if coverage >= 0.75:
        return "PARTIAL_COVERAGE"
    return "LOW_COVERAGE"

def validate_historical_environment(df: pd.DataFrame) -> None:
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    if not df["year"].between(2010, 2020).all():
        raise ValueError("Historical Environment must contain only 2010-2020")
    if set(df["asl"]) - set(ASLS):
        raise ValueError("Unknown ASL")
    allowed = set(CORE_POLLUTANTS + EXTENDED_POLLUTANTS)
    if set(df["pollutant"]) - allowed:
        raise ValueError("Unknown pollutant")
    if df.duplicated(["year","asl","pollutant"]).any():
        raise ValueError("Logical duplicates found")
    if df["mean_value"].isna().any():
        raise ValueError("Null mean_value found")
    if (df["station_count"] <= 0).any():
        raise ValueError("station_count must be > 0")
    if not df["coverage"].between(0.0, 1.0).all():
        raise ValueError("coverage must be in [0,1]")
    expected = df["coverage"].map(quality_from_coverage)
    if not expected.equals(df["quality_status"]):
        raise ValueError("quality_status inconsistent with coverage")

def build_historical_environment(
    source_csv: Path,
    output_parquet: Path,
) -> pd.DataFrame:
    """Validate the profiled historical source and materialize curated Parquet."""
    df = pd.read_csv(source_csv)
    validate_historical_environment(df)
    df = df.sort_values(["year","asl","pollutant"]).reset_index(drop=True)
    output_parquet.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_parquet, index=False)
    return df

def load_historical_environment(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    validate_historical_environment(df)
    return df.sort_values(["year","asl","pollutant"]).reset_index(drop=True)

def build_ml_environment_view(
    df: pd.DataFrame,
    min_coverage: float = 0.75,
    pollutants: tuple[str, ...] = CORE_POLLUTANTS,
) -> pd.DataFrame:
    """Filter admissible ML rows without mutating the curated dataset."""
    validate_historical_environment(df)
    return (
        df.loc[df["pollutant"].isin(pollutants) & (df["coverage"] >= min_coverage)]
          .sort_values(["year","asl","pollutant"])
          .reset_index(drop=True)
    )
