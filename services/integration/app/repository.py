from pathlib import Path

import pandas as pd


MASTER_DATASET_PATH = Path(
    "data/processed/one_health/"
    "one_health_master_2021_2023.parquet"
)


class IntegrationRepository:
    def __init__(
        self,
        dataset_path: Path = MASTER_DATASET_PATH,
    ):
        self.dataset_path = dataset_path

    def load(self) -> pd.DataFrame:
        if not self.dataset_path.exists():
            raise FileNotFoundError(
                "One Health Master Dataset "
                f"non trovato: {self.dataset_path}"
            )

        frame = pd.read_parquet(
            self.dataset_path
        )

        if frame.empty:
            raise ValueError(
                "Il One Health Master Dataset è vuoto."
            )

        return frame

    def filter(
        self,
        *,
        indicator_code: str | None = None,
        year: int | None = None,
        asl: str | None = None,
        sex: str | None = None,
        age_group: str | None = None,
    ) -> pd.DataFrame:

        frame = self.load().copy()

        if indicator_code is not None:
            frame = frame[
                frame["indicator_code"]
                .astype(str)
                == indicator_code
            ]

        if year is not None:
            frame = frame[
                frame["year"] == year
            ]

        if asl is not None:
            frame = frame[
                frame["asl"]
                .astype(str)
                == asl
            ]

        if sex is not None:
            frame = frame[
                frame["sex"]
                .astype(str)
                == sex
            ]

        if age_group is not None:
            frame = frame[
                frame["age_group"]
                .astype(str)
                == age_group
            ]

        return frame.reset_index(
            drop=True
        )