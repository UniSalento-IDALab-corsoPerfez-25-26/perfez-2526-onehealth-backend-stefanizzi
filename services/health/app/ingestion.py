from pathlib import Path

import pandas as pd

from etl.pipelines.health import (
    combine_health_indicators,
    run_health_indicator_pipeline,
)


class HealthIngestionService:
    """
    Adapter tra Health Service
    e core ETL sanitario.
    """

    def run_indicator(
        self,
        *,
        indicator_code: str,
        source_paths: list[Path],
    ) -> dict:

        output_path = (
            run_health_indicator_pipeline(
                source_paths=source_paths,
                indicator_code=indicator_code,
            )
        )

        frame = pd.read_parquet(
            output_path
        )

        return {
            "status": "OK",
            "indicator_code":
                indicator_code,
            "dataset_path":
                str(output_path),
            "record_count":
                len(frame),
        }

    def combine(
        self,
        *,
        input_paths: list[Path],
    ) -> dict:

        output_path = (
            combine_health_indicators(
                input_paths=input_paths,
            )
        )

        frame = pd.read_parquet(
            output_path
        )

        return {
            "status": "OK",
            "dataset_path":
                str(output_path),
            "record_count":
                len(frame),
        }

    from pathlib import Path

import pandas as pd

from etl.pipelines.health import (
    combine_health_indicators,
    run_health_indicator_pipeline,
)


class HealthIngestionService:
    def run(self) -> dict:
        jobs = {
            "BPCO": [
                Path("data/raw/health/bpco_2020_2022.csv"),
                Path("data/raw/health/bpco_2023.csv"),
            ],
            "DIABETES": [
                Path("data/raw/health/diabetes_2020_2022.csv"),
                Path("data/raw/health/diabetes_2023.csv"),
            ],
            "HYPERTENSION": [
                Path("data/raw/health/hypertension_2020_2022.csv"),
                Path("data/raw/health/hypertension_2023.csv"),
            ],
            "HEART_FAILURE": [
                Path("data/raw/health/heart_failure_2020_2022.csv"),
                Path("data/raw/health/heart_failure_2023.csv"),
            ],
        }

        outputs = []

        for indicator_code, source_paths in jobs.items():
            output_path = run_health_indicator_pipeline(
                source_paths=source_paths,
                indicator_code=indicator_code,
            )

            outputs.append(output_path)

        master_path = combine_health_indicators(
            input_paths=outputs
        )

        frame = pd.read_parquet(master_path)

        quality_counts = (
            frame["quality_status"]
            .value_counts(dropna=False)
            .to_dict()
        )

        duplicate_count = int(
            frame.duplicated(
                subset=[
                    "indicator_code",
                    "year",
                    "geographic_level",
                    "geographic_area",
                    "sex",
                    "age_group",
                ],
                keep=False,
            ).sum()
        )

        return {
            "status": "OK",
            "dataset_path": str(master_path),
            "record_count": len(frame),
            "indicators": sorted(
                frame["indicator_code"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            ),
            "years": sorted(
                frame["year"]
                .dropna()
                .astype(int)
                .unique()
                .tolist()
            ),
            "quality_status": {
                str(key): int(value)
                for key, value in quality_counts.items()
            },
            "logical_duplicates": duplicate_count,
        }