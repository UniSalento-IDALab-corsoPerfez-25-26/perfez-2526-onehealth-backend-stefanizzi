from pathlib import Path

import pandas as pd

from etl.transformers.meteorology_asl import (
    build_meteorology_asl_year,
)


def test_meteorology_asl_pipeline(
    tmp_path,
):
    daily_path = Path(
        "data/processed/meteorology/"
        "meteorology_standard_2023_daily.parquet"
    )

    output_path = (
        tmp_path
        / "meteorology_asl_2023_test.parquet"
    )

    frame = build_meteorology_asl_year(
        daily_path=daily_path,
        output_path=output_path,
        year=2023,
    )

    assert output_path.exists()

    assert len(frame) == 5

    assert set(
        frame["asl"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    ) == {
        "Bari",
        "Brindisi",
        "Foggia",
        "Lecce",
        "Taranto",
    }

    assert (
        frame["year"]
        .dropna()
        .astype(int)
        .unique()
        .tolist()
        == [2023]
    )

    quality = (
        frame["meteo_quality_status"]
        .value_counts()
        .to_dict()
    )

    assert quality == {
        "PARTIAL_COVERAGE": 4,
        "VALID": 1,
    }

    duplicates = frame.duplicated(
        subset=[
            "year",
            "asl",
        ],
        keep=False,
    )

    assert int(
        duplicates.sum()
    ) == 0