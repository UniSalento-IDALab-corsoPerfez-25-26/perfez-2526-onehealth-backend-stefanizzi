import pandas as pd

from services.meteorology.app.repository import (
    MeteorologyRepository,
)


class MeteorologyService:
    def __init__(
        self,
        repository: MeteorologyRepository | None = None,
    ):
        self.repository = (
            repository
            or MeteorologyRepository()
        )

    def get_meteorology(
        self,
        *,
        year: int | None = None,
        asl: str | None = None,
    ) -> list[dict]:

        frame = self.repository.filter(
            year=year,
            asl=asl,
        )

        frame = frame.astype(object)

        frame = frame.where(
            pd.notna(frame),
            None,
        )

        return frame.to_dict(
            orient="records"
        )

    def get_summary(self) -> dict:
        frame = self.repository.load()

        return {
            "record_count": len(frame),

            "years": sorted(
                frame["year"]
                .dropna()
                .astype(int)
                .unique()
                .tolist()
            ),

            "areas": sorted(
                frame["asl"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            ),

            "available_variables": sorted(
                {
                    variable.strip()
                    for value in (
                        frame["meteo_available_variables"]
                        .dropna()
                        .astype(str)
                    )
                    for variable in value.split(",")
                    if variable.strip()
                }
            ),
        }

    def get_quality(self) -> dict:
        frame = self.repository.load()

        quality_counts = (
            frame["meteo_quality_status"]
            .value_counts(dropna=False)
            .to_dict()
        )

        duplicate_count = int(
            frame.duplicated(
                subset=[
                    "year",
                    "asl",
                ],
                keep=False,
            ).sum()
        )

        full_year_count = 0

        if "meteo_is_full_year" in frame.columns:
            full_year_count = int(
                frame["meteo_is_full_year"]
                .fillna(False)
                .astype(bool)
                .sum()
            )

        return {
            "record_count": len(frame),

            "quality_status": {
                str(key): int(value)
                for key, value
                in quality_counts.items()
            },

            "full_year_records":
                full_year_count,

            "partial_year_records":
                len(frame) - full_year_count,

            "logical_duplicates":
                duplicate_count,
        }