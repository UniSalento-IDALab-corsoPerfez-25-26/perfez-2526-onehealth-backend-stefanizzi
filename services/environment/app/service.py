import pandas as pd

from services.environment.app.repository import (
    EnvironmentRepository,
)


class EnvironmentService:
    def __init__(
        self,
        repository: EnvironmentRepository | None = None,
    ):
        self.repository = (
            repository
            or EnvironmentRepository()
        )

    def get_exposure(
        self,
        *,
        year: int | None = None,
        asl: str | None = None,
        pollutant_code: str | None = None,
    ) -> list[dict]:

        frame = self.repository.filter(
            year=year,
            asl=asl,
            pollutant_code=pollutant_code,
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

            "pollutants": sorted(
                frame["pollutant_code"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            ),
        }

    def get_quality(self) -> dict:
        frame = self.repository.load()

        quality_counts = (
            frame["quality_status"]
            .value_counts(dropna=False)
            .to_dict()
        )

        duplicate_count = int(
            frame.duplicated(
                subset=[
                    "year",
                    "asl",
                    "pollutant_code",
                ],
                keep=False,
            ).sum()
        )

        return {
            "record_count": len(frame),

            "quality_status": {
                str(key): int(value)
                for key, value
                in quality_counts.items()
            },

            "logical_duplicates":
                duplicate_count,
        }