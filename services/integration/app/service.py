import pandas as pd

from services.integration.app.repository import (
    IntegrationRepository,
)


class IntegrationService:
    def __init__(
        self,
        repository: IntegrationRepository | None = None,
    ):
        self.repository = (
            repository
            or IntegrationRepository()
        )

    def get_master(
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

            "indicators": sorted(
                frame["indicator_code"]
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

        duplicate_count = int(
            frame.duplicated(
                subset=[
                    "indicator_code",
                    "year",
                    "asl",
                    "sex",
                    "age_group",
                ],
                keep=False,
            ).sum()
        )

        result = {
            "record_count": len(frame),
            "logical_duplicates": duplicate_count,
        }

        if (
            "integration_quality_status"
            in frame.columns
        ):
            quality_counts = (
                frame[
                    "integration_quality_status"
                ]
                .value_counts(
                    dropna=False
                )
                .to_dict()
            )

            result[
                "integration_quality_status"
            ] = {
                str(key): int(value)
                for key, value
                in quality_counts.items()
            }

        return result