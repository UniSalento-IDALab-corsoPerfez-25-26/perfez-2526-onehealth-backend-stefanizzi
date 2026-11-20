from pathlib import Path

import pandas as pd

from etl.integration.one_health import (
    build_one_health_master,
)


DUPLICATE_KEY = [
    "indicator_code",
    "year",
    "asl",
    "sex",
    "age_group",
]


def test_master_integration_pipeline(
    tmp_path,
):
    one_health_path = Path(
        "data/processed/one_health/"
        "one_health_dataset_2021_2023.parquet"
    )

    meteorology_path = Path(
        "data/processed/meteorology/"
        "meteorology_asl_2023.parquet"
    )

    output_path = (
        tmp_path
        / "one_health_master_test.parquet"
    )

    frame = build_one_health_master(
        one_health_path=one_health_path,
        meteorology_path=meteorology_path,
        output_path=output_path,
    )

    assert output_path.exists()

    assert len(frame) == 2160

    assert set(
        frame["year"]
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    ) == {
        2021,
        2022,
        2023,
    }

    assert set(
        frame["indicator_code"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    ) == {
        "BPCO",
        "DIABETES",
        "HEART_FAILURE",
        "HYPERTENSION",
    }

    duplicates = frame.duplicated(
        subset=DUPLICATE_KEY,
        keep=False,
    )

    assert int(
        duplicates.sum()
    ) == 0

    quality = (
        frame[
            "integration_quality_status"
        ]
        .value_counts()
        .to_dict()
    )

    assert quality == {
        "VALID_WITHOUT_METEO": 1560,
        "VALID_WITH_PARTIAL_METEO": 480,
        "VALID": 120,
    }

    assert int(
        frame["meteo_available"]
        .fillna(False)
        .astype(bool)
        .sum()
    ) == 600