from pathlib import Path

import pandas as pd


HISTORICAL_PATH = Path(
    "data/processed/meteorology/"
    "meteorology_asl_historical_2010_2025.parquet"
)

PARTIAL_2026_PATH = Path(
    "data/processed/meteorology/"
    "meteorology_asl_2026_partial.parquet"
)

VARIABLES = [
    "temperature_mean",
    "temperature_min",
    "temperature_max",
    "relative_humidity_mean",
    "wind_speed_mean",
    "surface_pressure_mean",
    "shortwave_radiation_mean",
    "cloud_cover_mean",
    "wind_direction_circular_mean",
]


class MeteorologyRepository:

    def __init__(self, dataset_path: Path = HISTORICAL_PATH):
        self.dataset_path = dataset_path

    def load(self) -> pd.DataFrame:
        if not self.dataset_path.is_file():
            raise FileNotFoundError(self.dataset_path)

        historical = pd.read_parquet(self.dataset_path).copy()

        if historical.empty:
            raise ValueError("Dataset meteorologico storico vuoto")

        historical["meteo_is_full_year"] = True

        frames = [historical]

        if PARTIAL_2026_PATH.is_file():
            partial = pd.read_parquet(PARTIAL_2026_PATH).copy()

            if (
                len(partial) != 6
                or not partial["year"].eq(2026).all()
                or not partial["quality_status"].eq(
                    "PROVISIONAL_PARTIAL_YEAR"
                ).all()
            ):
                raise ValueError("Dataset provvisorio 2026 non valido")

            partial["meteo_is_full_year"] = False
            frames.append(partial)

        result = pd.concat(frames, ignore_index=True)

        if result.duplicated(["year", "asl"]).any():
            raise ValueError("Duplicati anno/provincia")

        result["meteo_quality_status"] = result["quality_status"]

        result["meteo_available_variables"] = ",".join(VARIABLES)

        return result.sort_values(
            ["year", "asl"]
        ).reset_index(drop=True)

    def filter(
        self,
        *,
        year: int | None = None,
        asl: str | None = None,
    ) -> pd.DataFrame:
        frame = self.load()

        if year is not None:
            frame = frame[frame["year"] == year]

        if asl is not None:
            frame = frame[
                frame["asl"].astype(str).str.casefold()
                == asl.casefold()
            ]

        return frame.reset_index(drop=True)
