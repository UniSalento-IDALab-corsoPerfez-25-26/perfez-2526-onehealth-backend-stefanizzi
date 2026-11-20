from pathlib import Path

import pandas as pd


ENVIRONMENT_DATASET_PATH = Path(
    "data/processed/one_health/"
    "environmental_exposure_asl_2021_2023.parquet"
)


class EnvironmentRepository:
    def __init__(
        self,
        dataset_path: Path = ENVIRONMENT_DATASET_PATH,
    ):
        self.dataset_path = dataset_path

    def load(self) -> pd.DataFrame:
        if not self.dataset_path.exists():
            raise FileNotFoundError(
                "Dataset ambientale non trovato: "
                f"{self.dataset_path}"
            )

        frame = pd.read_parquet(
            self.dataset_path
        )

        if frame.empty:
            raise ValueError(
                "Il dataset ambientale è vuoto."
            )

        return frame

    def filter(
        self,
        *,
        year: int | None = None,
        asl: str | None = None,
        pollutant_code: str | None = None,
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

        if pollutant_code is not None:
            frame = frame[
                frame["pollutant_code"]
                .astype(str)
                .str.upper()
                == pollutant_code.upper()
            ]

        return frame.reset_index(
            drop=True
        )