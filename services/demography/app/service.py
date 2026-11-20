import pandas as pd

from services.demography.app.repository import (
    DemographyRepository,
)


class DemographyService:
    def __init__(
        self,
        repository: DemographyRepository | None = None,
    ):
        self.repository = (
            repository
            or DemographyRepository()
        )

    def get_population(
        self,
        *,
        year: int | None = None,
        asl: str | None = None,
        sex: str | None = None,
        age_group: str | None = None,
    ) -> list[dict]:

        frame = self.repository.filter(
            year=year,
            asl=asl,
            sex=sex,
            age_group=age_group,
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

            "sexes": sorted(
                frame["sex"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            ),

            "age_groups": sorted(
                frame["age_group"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            ),
        }

    def get_quality(self) -> dict:
        frame = self.repository.load()

        quality = (
            frame["quality_status"]
            .value_counts(dropna=False)
            .to_dict()
        )

        duplicate_count = int(
            frame.duplicated(
                subset=[
                    "year",
                    "asl",
                    "sex",
                    "age_group",
                ],
                keep=False,
            ).sum()
        )

        return {
            "record_count": len(frame),

            "quality_status": {
                str(key): int(value)
                for key, value
                in quality.items()
            },

            "logical_duplicates":
                duplicate_count,
        }