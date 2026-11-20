from pathlib import Path
import pandas as pd

from etl.transformers.one_health_ml_longitudinal import (
    aggregate_health_asl_year,
    build_longitudinal_ml_dataset,
)

HEALTH = Path("data/processed/health/health_prevalence_historical.parquet")
ENV_HIST = Path("data/processed/one_health/environmental_exposure_asl_historical.parquet")
ENV_CUR = Path("data/processed/one_health/environmental_exposure_asl_2021_2023.parquet")


def test_health_collapses_before_environment_join():
    health = pd.read_parquet(HEALTH)
    agg = aggregate_health_asl_year(health)
    assert agg.duplicated(["indicator_code","year","asl"]).sum() == 0
    assert set(agg["asl"]) == {"BAT","Bari","Brindisi","Foggia","Lecce","Taranto"}


def test_longitudinal_target_is_t_plus_1(tmp_path):
    out = tmp_path / "ml.parquet"
    ml = build_longitudinal_ml_dataset(
        HEALTH, ENV_HIST, ENV_CUR, out, min_historical_coverage=.75
    )
    assert out.exists()
    assert ml.duplicated(["indicator_code","year","asl"]).sum() == 0
    assert (ml["target_year"] == ml["year"] + 1).all()
    assert ml["year"].min() >= 2010
    assert ml["year"].max() <= 2022
    assert "target_prevalence_percent_t_plus_1" in ml
    assert "core_environment_complete" in ml
    assert ml["target_prevalence_percent_t_plus_1"].notna().all()


def test_no_sex_or_age_pseudoreplication(tmp_path):
    out = tmp_path / "ml.parquet"
    ml = build_longitudinal_ml_dataset(HEALTH, ENV_HIST, ENV_CUR, out)
    assert "sex" not in ml.columns
    assert "age_group" not in ml.columns
