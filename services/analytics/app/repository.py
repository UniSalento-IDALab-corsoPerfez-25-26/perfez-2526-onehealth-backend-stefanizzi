from pathlib import Path

import pandas as pd


MASTER_DATASET_PATH = Path(__file__).resolve().parents[3] / Path(
    "data/processed/one_health/"
    "one_health_master_2021_2023.parquet"
)


class AnalyticsRepository:
    """
    Accesso read-only al One Health Master Dataset.
    """

    def __init__(
        self,
        dataset_path: Path = MASTER_DATASET_PATH,
    ):
        self.dataset_path = dataset_path

    def load(self) -> pd.DataFrame:
        if not self.dataset_path.exists():
            raise FileNotFoundError(
                "One Health Master Dataset non trovato: "
                f"{self.dataset_path}"
            )

        frame = pd.read_parquet(
            self.dataset_path
        )

        if frame.empty:
            raise ValueError(
                "Il One Health Master Dataset è vuoto."
            )

        return frame