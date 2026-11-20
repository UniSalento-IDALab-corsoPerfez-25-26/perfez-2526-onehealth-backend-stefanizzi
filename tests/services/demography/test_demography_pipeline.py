from pathlib import Path

import pandas as pd

from etl.transformers.demography import (
    transform_population_years,
)


DUPLICATE_KEY = [
    "year",
    "asl",
    "sex",
    "age_group",
]


def test_complete_demography_pipeline(
    tmp_path,
):
    source_by_year = {
        2020: sorted(
            Path(
                "data/raw/demography/"
                "2020/extracted"
            ).glob(
                "POSAS_2020_it_*.csv"
            )
        ),
        2021: sorted(
            Path(
                "data/raw/demography/"
                "2021/extracted"
            ).glob(
                "POSAS_2021_it_*.csv"
            )
        ),
        2022: sorted(
            Path(
                "data/raw/demography/"
                "2022/extracted"
            ).glob(
                "POSAS_2022_it_*.csv"
            )
        ),
        2023: sorted(
            Path(
                "data/raw/demography/"
                "2023/extracted"
            ).glob(
                "POSAS_2023_it_*.csv"
            )
        ),
    }

    detail_path = (
        tmp_path
        / "population_puglia_test.parquet"
    )

    asl_path = (
        tmp_path
        / "population_asl_test.parquet"
    )

    transform_population_years(
        source_by_year=source_by_year,
        output_detail_path=detail_path,
        output_asl_path=asl_path,
    )

    assert detail_path.exists()
    assert asl_path.exists()

    detail = pd.read_parquet(
        detail_path
    )

    asl = pd.read_parquet(
        asl_path
    )

    assert not detail.empty

    assert len(asl) == 720

    assert set(
        asl["year"]
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

    assert set(
        asl["asl"]
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
        asl["sex"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    ) == {
        "ALL",
        "F",
        "M",
    }

    assert (
        asl["quality_status"]
        .eq("VALID")
        .all()
    )

    duplicates = asl.duplicated(
        subset=DUPLICATE_KEY,
        keep=False,
    )

    assert int(
        duplicates.sum()
    ) == 0