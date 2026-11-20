from pathlib import Path

import pandas as pd

from etl.pipelines.health import (
    combine_health_indicators,
    run_health_indicator_pipeline,
)


DUPLICATE_KEY = [
    "indicator_code",
    "year",
    "geographic_level",
    "geographic_area",
    "sex",
    "age_group",
]


def test_bpco_pipeline(tmp_path):
    output_path = run_health_indicator_pipeline(
        source_paths=[
            Path(
                "data/raw/health/"
                "bpco_2020_2022.csv"
            ),
            Path(
                "data/raw/health/"
                "bpco_2023.csv"
            ),
        ],
        indicator_code="BPCO",
        output_dir=tmp_path,
    )

    assert output_path.exists()

    frame = pd.read_parquet(
        output_path
    )

    assert not frame.empty

    assert (
        frame["indicator_code"]
        .dropna()
        .unique()
        .tolist()
        == ["BPCO"]
    )

    assert set(
        frame["year"]
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    ) == {
        2020,
        2021,
        2022,
        2023,
    }

    assert (
        frame["quality_status"]
        .eq("VALID")
        .all()
    )

    duplicates = frame.duplicated(
        subset=DUPLICATE_KEY,
        keep=False,
    )

    assert int(
        duplicates.sum()
    ) == 0


def test_complete_health_pipeline(
    tmp_path,
):
    jobs = {
        "BPCO": [
            Path(
                "data/raw/health/"
                "bpco_2020_2022.csv"
            ),
            Path(
                "data/raw/health/"
                "bpco_2023.csv"
            ),
        ],
        "DIABETES": [
            Path(
                "data/raw/health/"
                "diabetes_2020_2022.csv"
            ),
            Path(
                "data/raw/health/"
                "diabetes_2023.csv"
            ),
        ],
        "HYPERTENSION": [
            Path(
                "data/raw/health/"
                "hypertension_2020_2022.csv"
            ),
            Path(
                "data/raw/health/"
                "hypertension_2023.csv"
            ),
        ],
        "HEART_FAILURE": [
            Path(
                "data/raw/health/"
                "heart_failure_2020_2022.csv"
            ),
            Path(
                "data/raw/health/"
                "heart_failure_2023.csv"
            ),
        ],
    }

    outputs = []

    for indicator_code, paths in jobs.items():
        output = (
            run_health_indicator_pipeline(
                source_paths=paths,
                indicator_code=indicator_code,
                output_dir=tmp_path,
            )
        )

        outputs.append(output)

    master_path = (
        tmp_path
        / "health_master_test.parquet"
    )

    combine_health_indicators(
        input_paths=outputs,
        output_path=master_path,
    )

    frame = pd.read_parquet(
        master_path
    )

    assert len(frame) == 3000

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

    assert set(
        frame["year"]
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    ) == {
        2020,
        2021,
        2022,
        2023,
    }

    assert (
        frame["quality_status"]
        .eq("VALID")
        .all()
    )

    duplicates = frame.duplicated(
        subset=DUPLICATE_KEY,
        keep=False,
    )

    assert int(
        duplicates.sum()
    ) == 0