"""Build the leakage-aware longitudinal ML dataset for OneHealthAI.

Unit of analysis:
    ASL × year × indicator

Features at t:
    health prevalence at t
    population at t
    environmental exposure at t

Target:
    health prevalence at t+1

The builder deliberately:
- uses sex == ALL;
- aggregates age groups before joining Environment;
- never duplicates ASL-year environmental rows across sex/age strata;
- preserves environmental coverage metadata;
- does not overwrite frozen source datasets.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd

CORE_POLLUTANTS = ("PM10", "NO2", "O3")
OPTIONAL_POLLUTANTS = ("PM2.5",)
ASLS = ("BAT", "Bari", "Brindisi", "Foggia", "Lecce", "Taranto")


def _normalise_env_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise known historical/current Environment column aliases."""
    aliases = {
        "geographic_area": "asl",
        "area": "asl",
        "pollutant_code": "pollutant",
        "value": "mean_value",
        "annual_mean": "mean_value",
        "exposure_mean": "mean_value",
    }
    rename = {c: aliases[c] for c in df.columns if c in aliases}
    out = df.rename(columns=rename).copy()
    required = {"year", "asl", "pollutant", "mean_value"}
    missing = required - set(out.columns)
    if missing:
        raise ValueError(
            f"Environment schema not recognised; missing {sorted(missing)}. "
            f"Columns found: {list(df.columns)}"
        )
    out["pollutant"] = (
        out["pollutant"].astype(str).str.upper()
        .replace({"PM2,5": "PM2.5", "PM25": "PM2.5"})
    )
    return out


def combine_environment(
    historical_path: Path,
    current_path: Path,
) -> pd.DataFrame:
    hist = _normalise_env_columns(pd.read_parquet(historical_path))
    cur = _normalise_env_columns(pd.read_parquet(current_path))

    # Historical quality metadata exist by construction. Current frozen data
    # may use a different quality schema, so missing metadata remain explicit.
    for frame in (hist, cur):
        if "coverage" not in frame:
            frame["coverage"] = pd.NA
        if "station_count" not in frame:
            frame["station_count"] = pd.NA
        if "quality_status" not in frame:
            frame["quality_status"] = "UNKNOWN"

    keep = [
        "year", "asl", "pollutant", "mean_value",
        "coverage", "station_count", "quality_status",
    ]

    frames = []

    for frame in (hist, cur):
        selected = frame[keep].copy()

        # Remove columns that are entirely NA in this source before concat.
        # They are restored afterwards so the canonical schema is preserved.
        selected = selected.dropna(axis=1, how="all")
        frames.append(selected)

    env = pd.concat(frames, ignore_index=True)

    for column in keep:
        if column not in env.columns:
            env[column] = pd.NA

    env = env[keep]
    
    env = env[env["asl"].isin(ASLS)].copy()

    dup = env.duplicated(["year", "asl", "pollutant"], keep=False)
    if dup.any():
        rows = env.loc[dup, ["year","asl","pollutant"]].drop_duplicates()
        raise ValueError(f"Environment logical duplicates:\n{rows.to_string(index=False)}")

    return env.sort_values(["year","asl","pollutant"]).reset_index(drop=True)


def build_environment_wide(
    env: pd.DataFrame,
    min_historical_coverage: float = 0.75,
) -> pd.DataFrame:
    """One row per ASL-year; low-coverage historical values become missing.

    The source rows are never deleted or mutated. Filtering is applied only
    to this ML view.
    """
    x = env.copy()
    historical = x["year"].between(2010, 2020)
    known_cov = x["coverage"].notna()
    inadmissible = historical & known_cov & (x["coverage"] < min_historical_coverage)
    x.loc[inadmissible, "mean_value"] = pd.NA

    values = x.pivot(index=["year","asl"], columns="pollutant", values="mean_value")
    values.columns = [f"{c.lower().replace('.', '')}_mean" for c in values.columns]

    cov = x.pivot(index=["year","asl"], columns="pollutant", values="coverage")
    cov.columns = [f"{c.lower().replace('.', '')}_coverage" for c in cov.columns]

    wide = values.join(cov, how="outer").reset_index()
    return wide.sort_values(["year","asl"]).reset_index(drop=True)


def aggregate_health_asl_year(
    health: pd.DataFrame,
) -> pd.DataFrame:
    """Collapse age groups after selecting sex ALL.

    Cases and population are additive across mutually exclusive age bands.
    Prevalence is recomputed from the aggregated numerator/denominator.
    """
    required = {"indicator_code","year","asl","sex","age_group","cases","population"}
    missing = required - set(health.columns)
    if missing:
        raise ValueError(f"Health prevalence missing columns: {sorted(missing)}")

    h = health.loc[
        (health["sex"] == "ALL") & health["asl"].isin(ASLS)
    ].copy()

    # Guard against duplicate age-band rows before aggregation.
    keys = ["indicator_code","year","asl","sex","age_group"]
    if h.duplicated(keys).any():
        raise ValueError("Duplicate Health age-band rows found")

    agg = (
        h.groupby(["indicator_code","year","asl"], as_index=False)
         .agg(cases=("cases","sum"), population=("population","sum"))
    )
    if (agg["population"] <= 0).any():
        raise ValueError("Non-positive population in aggregated Health")

    agg["prevalence_percent"] = 100.0 * agg["cases"] / agg["population"]
    agg["prevalence_per_1000"] = 1000.0 * agg["cases"] / agg["population"]
    return agg


def build_longitudinal_ml_dataset(
    health_path: Path,
    historical_environment_path: Path,
    current_environment_path: Path,
    output_path: Path,
    min_historical_coverage: float = 0.75,
) -> pd.DataFrame:
    health = pd.read_parquet(health_path)
    h = aggregate_health_asl_year(health)

    env = combine_environment(
        historical_environment_path,
        current_environment_path,
    )
    e = build_environment_wide(env, min_historical_coverage)

    # Current-state feature table. Environment is joined only after Health
    # has been collapsed to ASL-year-indicator.
    current = h.merge(e, on=["year","asl"], how="left", validate="many_to_one")

    target = h[["indicator_code","year","asl","prevalence_percent"]].copy()
    target["year"] = target["year"] - 1
    target = target.rename(
        columns={"prevalence_percent": "target_prevalence_percent_t_plus_1"}
    )

    ml = current.merge(
        target,
        on=["indicator_code","year","asl"],
        how="inner",
        validate="one_to_one",
    )

    # Keep only years for which Environment is in the historical/current window.
    ml = ml[ml["year"].between(2010, 2022)].copy()
    ml["target_year"] = ml["year"] + 1

    # Core Environment completeness is explicit; do not silently impute.
    core_cols = ["pm10_mean","no2_mean","o3_mean"]
    for c in core_cols:
        if c not in ml:
            ml[c] = pd.NA
    ml["core_environment_complete"] = ml[core_cols].notna().all(axis=1)

    if ml.duplicated(["indicator_code","year","asl"]).any():
        raise ValueError("Logical duplicates in longitudinal ML dataset")

    ml = ml.sort_values(["indicator_code","year","asl"]).reset_index(drop=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ml.to_parquet(output_path, index=False)
    return ml
