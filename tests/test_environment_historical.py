from pathlib import Path
from etl.transformers.environment_historical import (
    build_historical_environment, build_ml_environment_view,
    load_historical_environment, validate_historical_environment,
)

CSV = Path("data/processed/one_health/environmental_exposure_asl_historical_2010_2020.csv")
PARQUET = Path("data/processed/one_health/environmental_exposure_asl_historical.parquet")

def test_build_and_validate_historical_environment(tmp_path):
    out = tmp_path / "environment.parquet"
    df = build_historical_environment(CSV, out)
    assert len(df) == 252
    assert df.duplicated(["year","asl","pollutant"]).sum() == 0
    assert df.year.min() == 2010
    assert df.year.max() == 2020

def test_quality_and_ml_view():
    df = build_historical_environment(CSV, PARQUET)
    validate_historical_environment(df)
    ml = build_ml_environment_view(df, min_coverage=.75)
    assert set(ml.pollutant).issubset({"PM10","NO2","O3"})
    assert (ml.coverage >= .75).all()
    assert ml.duplicated(["year","asl","pollutant"]).sum() == 0
