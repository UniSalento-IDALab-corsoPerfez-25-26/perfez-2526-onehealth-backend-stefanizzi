from pathlib import Path

import pandas as pd

from etl.integration.one_health import (
    build_one_health_master,
)
from etl.pipelines.one_health import (
    run_one_health_pipeline,
)


PROCESSED_ONE_HEALTH = Path(
    "data/processed/one_health"
)

METEOROLOGY_PATH = Path(
    "data/processed/meteorology/"
    "meteorology_asl_2023.parquet"
)


class IntegrationIngestionService:
    """
    Adapter tra Integration Service
    e core ETL One Health.
    """

    def run(
        self,
        *,
        start_year: int = 2021,
        end_year: int = 2023,
    ) -> dict:

        # -----------------------------------------------------
        # 1. Costruzione dataset One Health
        #    Health + Demography + Environment
        # -----------------------------------------------------

        one_health_path = (
            run_one_health_pipeline(
                start_year=start_year,
                end_year=end_year,
            )
        )

        # -----------------------------------------------------
        # 2. Integrazione meteorologia
        # -----------------------------------------------------

        master_path = (
            PROCESSED_ONE_HEALTH
            / (
                "one_health_master_"
                f"{start_year}_{end_year}.parquet"
            )
        )

        master = build_one_health_master(
            one_health_path=one_health_path,
            meteorology_path=METEOROLOGY_PATH,
            output_path=master_path,
        )

        # -----------------------------------------------------
        # 3. Verifica duplicati
        # -----------------------------------------------------

        duplicate_count = int(
            master.duplicated(
                subset=[
                    "indicator_code",
                    "year",
                    "asl",
                    "sex",
                    "age_group",
                ],
                keep=False,
            ).sum()
        )

        # -----------------------------------------------------
        # 4. Quality summary
        # -----------------------------------------------------

        quality_status = {}

        if (
            "integration_quality_status"
            in master.columns
        ):
            counts = (
                master[
                    "integration_quality_status"
                ]
                .value_counts(
                    dropna=False
                )
                .to_dict()
            )

            quality_status = {
                str(key): int(value)
                for key, value
                in counts.items()
            }

        # -----------------------------------------------------
        # 5. Copertura meteorologica
        # -----------------------------------------------------

        meteo_records = 0
        no_meteo_records = 0

        if (
            "meteo_quality_status"
            in master.columns
        ):
            meteo_records = int(
                master[
                    "meteo_quality_status"
                ]
                .notna()
                .sum()
            )

            no_meteo_records = (
                len(master)
                - meteo_records
            )

        # -----------------------------------------------------
        # 6. Risposta
        # -----------------------------------------------------

        return {
            "status": "OK",

            "dataset_path":
                str(master_path),

            "record_count":
                len(master),

            "years": sorted(
                master["year"]
                .dropna()
                .astype(int)
                .unique()
                .tolist()
            ),

            "areas": sorted(
                master["asl"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            ),

            "indicators": sorted(
                master["indicator_code"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            ),

            "records_with_meteorology":
                meteo_records,

            "records_without_meteorology":
                no_meteo_records,

            "integration_quality_status":
                quality_status,

            "logical_duplicates":
                duplicate_count,
        }