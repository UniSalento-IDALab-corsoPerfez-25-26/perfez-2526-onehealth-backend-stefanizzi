from pathlib import Path

import pandas as pd

from etl.transformers.one_health import (
    build_environmental_exposure,
)


DUPLICATE_KEY = [
    "year",
    "asl",
    "pollutant_code",
]


def test_complete_environment_pipeline(
    tmp_path,
):
    long_path = (
        tmp_path
        / "environment_long_test.parquet"
    )

    wide_path = (
        tmp_path
        / "environment_wide_test.parquet"
    )

    long_frame, wide_frame = (
        build_environmental_exposure(
            start_year=2021,
            end_year=2023,
            output_long_path=long_path,
            output_wide_path=wide_path,
        )
    )

    assert long_path.exists()
    assert wide_path.exists()

    assert len(long_frame) == 72
    assert len(wide_frame) == 18

    assert set(
        long_frame["year"]
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
        long_frame["asl"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    ) == {
        "BAT",
        "Bari",
        "Brindisi",
        "Foggia",
        "Lecce",
        "Taranto",
    }

    assert set(
        long_frame["pollutant_code"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    ) == {
        "NO2",
        "O3",
        "PM10",
        "PM2.5",
    }

    assert (
        long_frame["quality_status"]
        .eq("VALID")
        .all()
    )

    duplicates = (
        long_frame.duplicated(
            subset=DUPLICATE_KEY,
            keep=False,
        )
    )

    assert int(
        duplicates.sum()
    ) == 0