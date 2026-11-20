from pathlib import Path

import pandas as pd

from etl.transformers.demography import (
    transform_population_years,
)


DETAIL_OUTPUT_PATH = Path(
    "data/processed/demography/"
    "population_puglia_2020_2023.parquet"
)

ASL_OUTPUT_PATH = Path(
    "data/processed/demography/"
    "population_asl_2020_2023.parquet"
)


class DemographyIngestionService:
    """
    Adapter tra Demography Service
    e core ETL demografico ISTAT.
    """

    def run(self) -> dict:
        source_by_year = {}

        for year in range(2020, 2024):
            source_dir = Path(
                f"data/raw/demography/"
                f"{year}/extracted"
            )

            source_paths = sorted(
                source_dir.glob(
                    f"POSAS_{year}_it_*.csv"
                )
            )

            if not source_paths:
                raise FileNotFoundError(
                    "Nessun file ISTAT trovato "
                    f"per l'anno {year} in "
                    f"{source_dir}"
                )

            source_by_year[year] = (
                source_paths
            )

        transform_population_years(
            source_by_year=source_by_year,
            output_detail_path=(
                DETAIL_OUTPUT_PATH
            ),
            output_asl_path=(
                ASL_OUTPUT_PATH
            ),
        )

        frame = pd.read_parquet(
            ASL_OUTPUT_PATH
        )

        quality_counts = (
            frame["quality_status"]
            .value_counts(dropna=False)
            .to_dict()
        )

        duplicate_count = int(
            frame.duplicated(
                subset=[
                    "year",
                    "asl",
                    "sex",
                    "age_group",
                ],
                keep=False,
            ).sum()
        )

        return {
            "status": "OK",
            "detail_dataset_path":
                str(DETAIL_OUTPUT_PATH),
            "asl_dataset_path":
                str(ASL_OUTPUT_PATH),
            "record_count":
                len(frame),
            "years": sorted(
                frame["year"]
                .dropna()
                .astype(int)
                .unique()
                .tolist()
            ),
            "areas": sorted(
                frame["asl"]
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
            "logical_duplicates":
                duplicate_count,
        }