import pandas as pd

from services.health.app.repository import (
    HealthRepository,
)


class HealthService:
    """
    Logica applicativa esposta dal microservizio.

    Il servizio utilizza i dataset prodotti
    dal core ETL.
    """

    def __init__(
        self,
        repository: HealthRepository | None = None,
    ):
        self.repository = (
            repository
            or HealthRepository()
        )

    def get_indicators(
        self,
    ) -> list[str]:

        frame = self.repository.load()

        return sorted(
            frame["indicator_code"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

    def get_cases(
        self,
        *,
        indicator_code: str | None = None,
        year: int | None = None,
        asl: str | None = None,
        sex: str | None = None,
        age_group: str | None = None,
    ) -> list[dict]:

        frame = self.repository.filter(
            indicator_code=indicator_code,
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

    def get_summary(
        self,
    ) -> dict:

        frame = self.repository.load()

        return {
            "record_count": len(frame),

            "indicators": sorted(
                frame["indicator_code"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            ),

            "years": sorted(
                frame["year"]
                .dropna()
                .astype(int)
                .unique()
                .tolist()
            ),

            "areas": sorted(
                frame["geographic_area"]
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

    def get_quality(
        self,
    ) -> dict:

        frame = self.repository.load()

        quality = (
            frame["quality_status"]
            .value_counts(dropna=False)
            .to_dict()
        )

        duplicates = frame.duplicated(
            subset=[
                "indicator_code",
                "year",
                "geographic_level",
                "geographic_area",
                "sex",
                "age_group",
            ],
            keep=False,
        ).sum()

        return {
            "record_count": len(frame),

            "quality_status": {
                str(key): int(value)
                for key, value
                in quality.items()
            },

            "logical_duplicates":
                int(duplicates),
        }