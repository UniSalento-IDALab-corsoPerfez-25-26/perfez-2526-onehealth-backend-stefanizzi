import math

import pandas as pd

from services.analytics.app.repository import (
    AnalyticsRepository,
)


ENVIRONMENTAL_MEAN_COLUMNS = [
    "no2_mean_value",
    "o3_mean_value",
    "pm10_mean_value",
    "pm2_5_mean_value",
]


class AnalyticsService:
    def __init__(
        self,
        repository: AnalyticsRepository | None = None,
    ):
        self.repository = (
            repository
            or AnalyticsRepository()
        )

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def _json_safe(
        frame: pd.DataFrame,
    ) -> list[dict]:

        result = frame.astype(object)

        result = result.where(
            pd.notna(result),
            None,
        )

        return result.to_dict(
            orient="records"
        )

    @staticmethod
    def _filter(
        frame: pd.DataFrame,
        *,
        indicator_code: str | None = None,
        year: int | None = None,
        asl: str | None = None,
        sex: str | None = None,
        age_group: str | None = None,
    ) -> pd.DataFrame:

        result = frame.copy()

        if indicator_code is not None:
            result = result[
                result["indicator_code"]
                .astype(str)
                == indicator_code
            ]

        if year is not None:
            result = result[
                result["year"] == year
            ]

        if asl is not None:
            result = result[
                result["asl"]
                .astype(str)
                == asl
            ]

        if sex is not None:
            result = result[
                result["sex"]
                .astype(str)
                == sex
            ]

        if age_group is not None:
            result = result[
                result["age_group"]
                .astype(str)
                == age_group
            ]

        return result

    # =========================================================
    # Summary
    # =========================================================

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

            "available_environmental_variables": [
                column
                for column
                in ENVIRONMENTAL_MEAN_COLUMNS
                if column in frame.columns
            ],
        }

    # =========================================================
    # KPI
    # =========================================================

    def get_kpi(
        self,
        *,
        indicator_code: str,
        year: int,
        asl: str | None = None,
        sex: str = "ALL",
    ) -> dict:

        frame = self.repository.load()

        frame = self._filter(
            frame,
            indicator_code=indicator_code,
            year=year,
            asl=asl,
            sex=sex,
        )

        if frame.empty:
            return {
                "status": "NO_DATA",
                "indicator_code": indicator_code,
                "year": year,
                "asl": asl,
            }

        total_cases = int(
            frame["cases"]
            .fillna(0)
            .sum()
        )

        total_population = int(
            frame["population"]
            .fillna(0)
            .sum()
        )

        prevalence_per_1000 = None

        if total_population > 0:
            prevalence_per_1000 = round(
                total_cases
                / total_population
                * 1000,
                4,
            )

        return {
            "status": "OK",
            "indicator_code": indicator_code,
            "year": year,
            "asl": asl,
            "sex": sex,
            "cases": total_cases,
            "population": total_population,
            "prevalence_per_1000":
                prevalence_per_1000,
        }

    # =========================================================
    # Trend
    # =========================================================

    def get_trend(
        self,
        *,
        indicator_code: str,
        asl: str,
        sex: str = "ALL",
    ) -> list[dict]:

        frame = self.repository.load()

        frame = self._filter(
            frame,
            indicator_code=indicator_code,
            asl=asl,
            sex=sex,
        )

        if frame.empty:
            return []

        grouped = (
            frame.groupby(
                "year",
                as_index=False,
            )
            .agg(
                cases=(
                    "cases",
                    "sum",
                ),
                population=(
                    "population",
                    "sum",
                ),
            )
        )

        grouped[
            "prevalence_per_1000"
        ] = (
            grouped["cases"]
            / grouped["population"]
            * 1000
        ).round(4)

        grouped = grouped.sort_values(
            "year"
        )

        return self._json_safe(
            grouped
        )

    # =========================================================
    # Territorial ranking
    # =========================================================

    def get_territorial_ranking(
        self,
        *,
        indicator_code: str,
        year: int,
        sex: str = "ALL",
    ) -> list[dict]:

        frame = self.repository.load()

        frame = self._filter(
            frame,
            indicator_code=indicator_code,
            year=year,
            sex=sex,
        )

        if frame.empty:
            return []

        grouped = (
            frame.groupby(
                "asl",
                as_index=False,
            )
            .agg(
                cases=(
                    "cases",
                    "sum",
                ),
                population=(
                    "population",
                    "sum",
                ),
            )
        )

        grouped[
            "prevalence_per_1000"
        ] = (
            grouped["cases"]
            / grouped["population"]
            * 1000
        ).round(4)

        grouped = (
            grouped.sort_values(
                "prevalence_per_1000",
                ascending=False,
            )
            .reset_index(
                drop=True
            )
        )

        grouped["rank"] = (
            grouped.index + 1
        )

        return self._json_safe(
            grouped[
                [
                    "rank",
                    "asl",
                    "cases",
                    "population",
                    "prevalence_per_1000",
                ]
            ]
        )

    # =========================================================
    # Dataset analitico ASL × anno × indicatore
    # =========================================================

    def build_analytical_dataset(
        self,
        *,
        indicator_code: str,
    ) -> pd.DataFrame:
        """
        Costruisce un dataset alla granularità:

            indicator × year × ASL

        evitando di trattare sex × age_group come
        osservazioni ambientali indipendenti.

        Per la componente sanitaria vengono utilizzati
        esclusivamente i record sex == ALL e le fasce
        d'età vengono aggregate.
        """

        frame = self.repository.load()

        frame = frame[
            (
                frame["indicator_code"]
                == indicator_code
            )
            & (
                frame["sex"]
                == "ALL"
            )
        ].copy()

        if frame.empty:
            return pd.DataFrame()

        health = (
            frame.groupby(
                [
                    "indicator_code",
                    "year",
                    "asl",
                ],
                as_index=False,
            )
            .agg(
                cases=(
                    "cases",
                    "sum",
                ),
                population=(
                    "population",
                    "sum",
                ),
            )
        )

        health[
            "prevalence_per_1000"
        ] = (
            health["cases"]
            / health["population"]
            * 1000
        )

        environmental_columns = [
            column
            for column
            in ENVIRONMENTAL_MEAN_COLUMNS
            if column in frame.columns
        ]

        additional_columns = []

        for column in [
            "meteo_year_coverage_percent",
            "meteo_precipitation_total_observed",
            "meteo_atmospheric_pressure_mean_observed",
            "integration_quality_status",
            "meteo_quality_status",
            "meteo_available",
        ]:
            if column in frame.columns:
                additional_columns.append(
                    column
                )

        context_columns = (
            environmental_columns
            + additional_columns
        )

        context = (
            frame[
                [
                    "year",
                    "asl",
                    *context_columns,
                ]
            ]
            .drop_duplicates(
                subset=[
                    "year",
                    "asl",
                ]
            )
        )

        result = health.merge(
            context,
            on=[
                "year",
                "asl",
            ],
            how="left",
            validate="many_to_one",
        )

        return result.sort_values(
            [
                "year",
                "asl",
            ]
        ).reset_index(
            drop=True
        )

    # =========================================================
    # Correlations
    # =========================================================

    def get_correlations(
        self,
        *,
        indicator_code: str,
    ) -> dict:

        analytical = (
            self.build_analytical_dataset(
                indicator_code=indicator_code,
            )
        )

        if analytical.empty:
            return {
                "status": "NO_DATA",
                "indicator_code":
                    indicator_code,
                "observations": 0,
                "correlations": [],
            }

        correlations = []

        for column in (
            ENVIRONMENTAL_MEAN_COLUMNS
        ):
            if column not in analytical.columns:
                continue

            valid = analytical[
                [
                    "prevalence_per_1000",
                    column,
                ]
            ].dropna()

            if len(valid) < 3:
                continue

            value = (
                valid[
                    "prevalence_per_1000"
                ]
                .corr(
                    valid[column],
                    method="pearson",
                )
            )

            if (
                value is None
                or math.isnan(value)
            ):
                continue

            correlations.append(
                {
                    "variable": column,
                    "method": "pearson",
                    "coefficient": round(
                        float(value),
                        4,
                    ),
                    "observations": len(valid),
                }
            )

        correlations = sorted(
            correlations,
            key=lambda item: abs(
                item["coefficient"]
            ),
            reverse=True,
        )

        return {
            "status": "OK",
            "indicator_code":
                indicator_code,
            "analytical_granularity":
                "ASL_YEAR_INDICATOR",
            "observations":
                len(analytical),
            "correlations":
                correlations,
            "warning": (
                "Correlations are descriptive "
                "associations and must not be "
                "interpreted as causal effects."
            ),
        }