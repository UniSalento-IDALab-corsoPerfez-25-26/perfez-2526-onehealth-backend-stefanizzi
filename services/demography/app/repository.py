from pathlib import Path

import pandas as pd


DEMOGRAPHY_DATASET_PATH = Path(
    "data/processed/demography/"
    "population_asl_operational_2006_2023.parquet"
)


class DemographyRepository:
    """
    Accesso al dataset demografico ASL
    prodotto dal core ETL.
    """

    def __init__(
        self,
        dataset_path: Path = DEMOGRAPHY_DATASET_PATH,
    ):
        self.dataset_path = dataset_path

    def load(self) -> pd.DataFrame:
        if not self.dataset_path.exists():
            raise FileNotFoundError(
                "Dataset demografico non trovato: "
                f"{self.dataset_path}"
            )

        frame = pd.read_parquet(
            self.dataset_path
        )

        if frame.empty:
            raise ValueError(
                "Il dataset demografico è vuoto."
            )

        return frame

    def filter(
        self,
        *,
        year: int | None = None,
        asl: str | None = None,
        sex: str | None = None,
        age_group: str | None = None,
    ) -> pd.DataFrame:

        frame = self.load().copy()

        if year is not None:
            frame = frame[
                frame["year"] == year
            ]

        if asl is not None:
            frame = frame[
                frame["asl"].astype(str)
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