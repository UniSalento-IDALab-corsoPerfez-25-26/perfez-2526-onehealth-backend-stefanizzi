from pathlib import Path

import pandas as pd


HEALTH_DATASET_PATH = Path(
    "data/processed/health/"
    "health_indicators_2020_2023.parquet"
)


class HealthRepository:
    """
    Accesso al dataset sanitario curato prodotto
    dalle pipeline ETL.

    Il repository NON contiene logica ETL.
    """

    def __init__(
        self,
        dataset_path: Path = HEALTH_DATASET_PATH,
    ):
        self.dataset_path = dataset_path

    def load(self) -> pd.DataFrame:
        if not self.dataset_path.exists():
            raise FileNotFoundError(
                f"Dataset sanitario non trovato: "
                f"{self.dataset_path}"
            )

        frame = pd.read_parquet(
            self.dataset_path
        )

        if frame.empty:
            raise ValueError(
                "Il dataset sanitario è vuoto."
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
                frame["indicator_code"].astype(str)
                == indicator_code
            ]

        if year is not None:
            frame = frame[
                frame["year"] == year
            ]

        if asl is not None:
            frame = frame[
                frame["geographic_area"].astype(str)
                == asl
            ]

        if sex is not None:
            frame = frame[
                frame["sex"].astype(str)
                == sex
            ]

        if age_group is not None:
            frame = frame[
                frame["age_group"].astype(str)
                == age_group
            ]

        return frame.reset_index(
            drop=True
        )