from pathlib import Path
from etl.transformers.one_health_ml_longitudinal import build_longitudinal_ml_dataset

df = build_longitudinal_ml_dataset(
    health_path=Path("data/processed/health/health_prevalence_historical.parquet"),
    historical_environment_path=Path("data/processed/one_health/environmental_exposure_asl_historical.parquet"),
    current_environment_path=Path("data/processed/one_health/environmental_exposure_asl_2021_2023.parquet"),
    output_path=Path("data/processed/one_health/one_health_ml_longitudinal_2010_2023.parquet"),
    min_historical_coverage=0.75,
)

print("shape:", df.shape)
print("years t:", df.year.min(), "-", df.year.max())
print("target years:", df.target_year.min(), "-", df.target_year.max())
print("indicators:", sorted(df.indicator_code.unique()))
print("ASL:", sorted(df.asl.unique()))
print("duplicates:", df.duplicated(["indicator_code","year","asl"]).sum())
print("core env complete:", df.core_environment_complete.value_counts().to_dict())
print("\\nrecords by indicator:")
print(df.groupby("indicator_code").size())
