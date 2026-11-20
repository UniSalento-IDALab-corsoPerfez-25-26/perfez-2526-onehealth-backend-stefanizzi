from pathlib import Path

from etl.transformers.one_health import (
    build_environmental_exposure,
)


LONG_OUTPUT_PATH = Path(
    "data/processed/one_health/"
    "environmental_exposure_asl_2021_2023.parquet"
)

WIDE_OUTPUT_PATH = Path(
    "data/processed/one_health/"
    "environmental_exposure_asl_2021_2023_wide.parquet"
)


class EnvironmentIngestionService:
    def run(self) -> dict:

        long_frame, wide_frame = (
            build_environmental_exposure(
                start_year=2021,
                end_year=2023,
                output_long_path=LONG_OUTPUT_PATH,
                output_wide_path=WIDE_OUTPUT_PATH,
            )
        )

        quality_counts = (
            long_frame["quality_status"]
            .value_counts(dropna=False)
            .to_dict()
        )

        duplicate_count = int(
            long_frame.duplicated(
                subset=[
                    "year",
                    "asl",
                    "pollutant_code",
                ],
                keep=False,
            ).sum()
        )

        return {
            "status": "OK",

            "long_dataset_path":
                str(LONG_OUTPUT_PATH),

            "wide_dataset_path":
                str(WIDE_OUTPUT_PATH),

            "record_count":
                len(long_frame),

            "wide_record_count":
                len(wide_frame),

            "years": sorted(
                long_frame["year"]
                .dropna()
                .astype(int)
                .unique()
                .tolist()
            ),

            "areas": sorted(
                long_frame["asl"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            ),

            "pollutants": sorted(
                long_frame["pollutant_code"]
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