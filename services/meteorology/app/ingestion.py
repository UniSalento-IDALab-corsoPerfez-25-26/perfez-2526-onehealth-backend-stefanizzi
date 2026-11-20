from pathlib import Path

import pandas as pd

from etl.pipelines.meteorology import (
    run_standard_meteorology_year,
)
from etl.transformers.meteorology_asl import (
    build_meteorology_asl_year,
)


PROCESSED_ROOT = Path(
    "data/processed/meteorology"
)

ASL_OUTPUT_PATH = (
    PROCESSED_ROOT
    / "meteorology_asl_2023.parquet"
)


class MeteorologyIngestionService:
    """
    Adapter tra Meteorology Service
    e core ETL meteorologico.
    """

    def run(
        self,
        *,
        year: int = 2023,
    ) -> dict:

        # -----------------------------------------------------
        # 1. Pipeline completa ARPA Meteo standard
        # -----------------------------------------------------

        hourly_path, daily_path = (
            run_standard_meteorology_year(
                year=year
            )
        )

        # -----------------------------------------------------
        # 2. Aggregazione ASL × anno
        # -----------------------------------------------------

        asl_output_path = (
            PROCESSED_ROOT
            / f"meteorology_asl_{year}.parquet"
        )

        asl_frame = (
            build_meteorology_asl_year(
                daily_path=daily_path,
                output_path=asl_output_path,
                year=year,
            )
        )

        # -----------------------------------------------------
        # 3. Quality summary
        # -----------------------------------------------------

        quality_counts = (
            asl_frame[
                "meteo_quality_status"
            ]
            .value_counts(
                dropna=False
            )
            .to_dict()
        )

        duplicate_count = int(
            asl_frame.duplicated(
                subset=[
                    "year",
                    "asl",
                ],
                keep=False,
            ).sum()
        )

        full_year_count = int(
            asl_frame[
                "meteo_is_full_year"
            ]
            .fillna(False)
            .astype(bool)
            .sum()
        )

        # -----------------------------------------------------
        # 4. Risposta API
        # -----------------------------------------------------

        return {
            "status": "OK",

            "year":
                year,

            "hourly_dataset_path":
                str(hourly_path),

            "daily_dataset_path":
                str(daily_path),

            "asl_dataset_path":
                str(asl_output_path),

            "record_count":
                len(asl_frame),

            "areas": sorted(
                asl_frame["asl"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            ),

            "quality_status": {
                str(key): int(value)
                for key, value
                in quality_counts.items()
            },

            "full_year_records":
                full_year_count,

            "partial_year_records":
                len(asl_frame)
                - full_year_count,

            "logical_duplicates":
                duplicate_count,
        }