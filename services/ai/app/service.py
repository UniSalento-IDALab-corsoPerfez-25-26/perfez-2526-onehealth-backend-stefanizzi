import math

import pandas as pd

from services.analytics.app.service import (
    AnalyticsService,
)


ENVIRONMENTAL_COLUMNS = [
    "no2_mean_value",
    "o3_mean_value",
    "pm10_mean_value",
    "pm2_5_mean_value",
]


class AIService:
    """
    Explainable decision-support layer.

    The service consumes the analytical dataset produced by
    AnalyticsService and applies a deterministic, transparent
    multi-criteria territorial prioritization method.

    The current implementation does not perform causal inference
    and does not produce individual clinical predictions.
    """

    MODEL_NAME = (
        "EXPLAINABLE_ONE_HEALTH_PRIORITY"
    )

    MODEL_VERSION = "1.0.0"

    HEALTH_WEIGHT = 0.5
    ENVIRONMENT_WEIGHT = 0.5

    def __init__(
        self,
        analytics_service: AnalyticsService | None = None,
        *,
        environment_weight: float = 0.5,
    ):
        if not 0 <= environment_weight <= 1:
            raise ValueError("environment_weight must be between 0 and 1")
        self.ENVIRONMENT_WEIGHT = environment_weight
        self.HEALTH_WEIGHT = 1 - environment_weight
        self.analytics_service = (
            analytics_service
            or AnalyticsService()
        )

    # =========================================================
    # JSON helpers
    # =========================================================

    @staticmethod
    def _json_safe(
        frame: pd.DataFrame,
    ) -> list[dict]:
        """
        Convert a DataFrame into JSON-safe records.

        Pandas missing values are converted to None.
        """

        result = frame.astype(object)

        result = result.where(
            pd.notna(result),
            None,
        )

        return result.to_dict(
            orient="records"
        )

    # =========================================================
    # Priority classification
    # =========================================================

    @staticmethod
    def _priority_level(
        rank: int,
        total: int,
    ) -> str:
        """
        Assign a relative territorial priority level.

        With six ASLs this produces:

            ranks 1-2 -> HIGH
            ranks 3-4 -> MEDIUM
            ranks 5-6 -> LOW

        These classes are relative to the territories included
        in the comparison and do not represent epidemiological
        or clinical thresholds.
        """

        if total <= 0:
            return "UNDEFINED"

        fraction = rank / total

        if fraction <= 1 / 3:
            return "HIGH"

        if fraction <= 2 / 3:
            return "MEDIUM"

        return "LOW"

    # =========================================================
    # Priority dataset
    # =========================================================

    def build_priority_dataset(
        self,
        *,
        indicator_code: str,
        year: int,
    ) -> pd.DataFrame:
        """
        Build the territorial priority dataset at granularity:

            indicator × year × ASL

        The health and environmental analytical representation
        is delegated to AnalyticsService.

        AIService applies only the explainable prioritization
        logic.

        Missing environmental or meteorological information is
        preserved as missing and is never converted to zero.
        """

        # -----------------------------------------------------
        # 1. Analytical dataset produced by AnalyticsService
        # -----------------------------------------------------

        dataset = (
            self.analytics_service
            .build_analytical_dataset(
                indicator_code=indicator_code
            )
        )

        if dataset.empty:
            return pd.DataFrame()

        # -----------------------------------------------------
        # 2. Requested year
        # -----------------------------------------------------

        dataset = dataset[
            dataset["year"] == year
        ].copy()

        if dataset.empty:
            return pd.DataFrame()

        # -----------------------------------------------------
        # 3. Defensive granularity validation
        # -----------------------------------------------------

        required_columns = [
            "indicator_code",
            "year",
            "asl",
            "cases",
            "population",
            "prevalence_per_1000",
        ]

        missing_columns = [
            column
            for column in required_columns
            if column not in dataset.columns
        ]

        if missing_columns:
            raise ValueError(
                "Analytical dataset is missing "
                "required columns: "
                f"{missing_columns}"
            )

        duplicate_count = int(
            dataset.duplicated(
                subset=[
                    "indicator_code",
                    "year",
                    "asl",
                ]
            ).sum()
        )

        if duplicate_count > 0:
            raise ValueError(
                "Analytical dataset contains "
                "duplicate ASL-year-indicator "
                "observations."
            )

        # -----------------------------------------------------
        # 4. Health component
        # -----------------------------------------------------

        dataset[
            "health_percentile"
        ] = (
            dataset[
                "prevalence_per_1000"
            ]
            .rank(
                pct=True,
                method="average",
            )
        )

        # -----------------------------------------------------
        # 5. Environmental component
        #
        # Each available pollutant is transformed into a
        # relative percentile within the selected year.
        #
        # The environmental component is the mean percentile
        # of the available pollutant variables.
        #
        # Missing values remain missing and are not interpreted
        # as zero exposure.
        # -----------------------------------------------------

        available_environmental_columns = [
            column
            for column in ENVIRONMENTAL_COLUMNS
            if column in dataset.columns
        ]

        pollutant_percentile_columns = []

        for column in (
            available_environmental_columns
        ):
            percentile_column = (
                f"{column}_percentile"
            )

            dataset[
                percentile_column
            ] = (
                dataset[column]
                .rank(
                    pct=True,
                    method="average",
                )
            )

            pollutant_percentile_columns.append(
                percentile_column
            )

        if pollutant_percentile_columns:
            dataset[
                "environment_percentile"
            ] = (
                dataset[
                    pollutant_percentile_columns
                ]
                .mean(
                    axis=1,
                    skipna=True,
                )
            )
        else:
            dataset[
                "environment_percentile"
            ] = math.nan

        # -----------------------------------------------------
        # 6. Explainable composite score
        #
        # Priority Score =
        #
        #   health_weight × health_percentile
        #   +
        #   environment_weight × environment_percentile
        #
        # scaled to 0-100.
        #
        # The score is calculated only where both components
        # are available.
        # -----------------------------------------------------

        valid_score_mask = (
            dataset[
                "health_percentile"
            ].notna()
            &
            dataset[
                "environment_percentile"
            ].notna()
        )

        dataset[
            "priority_score"
        ] = math.nan

        dataset.loc[
            valid_score_mask,
            "priority_score",
        ] = (
            (
                self.HEALTH_WEIGHT
                * dataset.loc[
                    valid_score_mask,
                    "health_percentile",
                ]
            )
            +
            (
                self.ENVIRONMENT_WEIGHT
                * dataset.loc[
                    valid_score_mask,
                    "environment_percentile",
                ]
            )
        ) * 100

        dataset[
            "priority_score"
        ] = dataset[
            "priority_score"
        ].round(2)

        # -----------------------------------------------------
        # 7. Territorial ranking
        #
        # Ties in priority_score are resolved using health
        # burden and then ASL name for deterministic output.
        # Missing scores are placed at the end.
        # -----------------------------------------------------

        dataset = (
            dataset.sort_values(
                by=[
                    "priority_score",
                    "prevalence_per_1000",
                    "asl",
                ],
                ascending=[
                    False,
                    False,
                    True,
                ],
                na_position="last",
            )
            .reset_index(
                drop=True
            )
        )

        valid_priority_count = int(
            dataset[
                "priority_score"
            ]
            .notna()
            .sum()
        )

        dataset[
            "priority_rank"
        ] = pd.Series(
            [pd.NA] * len(dataset),
            dtype="Int64",
        )

        if valid_priority_count > 0:
            dataset.loc[
                dataset[
                    "priority_score"
                ].notna(),
                "priority_rank",
            ] = range(
                1,
                valid_priority_count + 1,
            )

        # -----------------------------------------------------
        # 8. Relative priority level
        # -----------------------------------------------------

        def assign_priority_level(
            rank,
        ) -> str:
            if pd.isna(rank):
                return "UNDEFINED"

            return self._priority_level(
                int(rank),
                valid_priority_count,
            )

        dataset[
            "priority_level"
        ] = dataset[
            "priority_rank"
        ].apply(
            assign_priority_level
        )

        return dataset

    # =========================================================
    # Ranking endpoint logic
    # =========================================================

    def get_ranking(
        self,
        *,
        indicator_code: str,
        year: int,
    ) -> dict:
        """
        Return the territorial ranking for one indicator and year.
        """

        dataset = (
            self.build_priority_dataset(
                indicator_code=indicator_code,
                year=year,
            )
        )

        if dataset.empty:
            return {
                "status": "NO_DATA",
                "indicator_code":
                    indicator_code,
                "year":
                    year,
                "items": [],
                "count": 0,
            }

        output_columns = [
            "priority_rank",
            "asl",
            "priority_level",
            "priority_score",
            "cases",
            "population",
            "prevalence_per_1000",
            "health_percentile",
            "environment_percentile",
        ]

        optional_columns = [
            "integration_quality_status",
            "meteo_quality_status",
            "meteo_available",
            "meteo_year_coverage_percent",
        ]

        for column in optional_columns:
            if column in dataset.columns:
                output_columns.append(
                    column
                )

        result = dataset[
            output_columns
        ].copy()

        numeric_columns = [
            "priority_score",
            "prevalence_per_1000",
            "health_percentile",
            "environment_percentile",
            "meteo_year_coverage_percent",
        ]

        for column in numeric_columns:
            if column not in result.columns:
                continue

            result[column] = (
                pd.to_numeric(
                    result[column],
                    errors="coerce",
                )
                .round(4)
            )

        return {
            "status": "OK",

            "model":
                self.MODEL_NAME,

            "model_version":
                self.MODEL_VERSION,

            "indicator_code":
                indicator_code,

            "year":
                year,

            "health_weight":
                self.HEALTH_WEIGHT,

            "environment_weight":
                self.ENVIRONMENT_WEIGHT,

            "items":
                self._json_safe(
                    result
                ),

            "count":
                len(result),

            "interpretation": (
                "Priority is relative to the "
                "territories available for the "
                "selected indicator and year."
            ),
        }

    # =========================================================
    # Single territorial priority
    # =========================================================

    def get_priority(
        self,
        *,
        indicator_code: str,
        year: int,
        asl: str,
    ) -> dict:
        """
        Return the priority result for one ASL.
        """

        ranking = self.get_ranking(
            indicator_code=indicator_code,
            year=year,
        )

        if ranking["status"] != "OK":
            return {
                "status": "NO_DATA",
                "indicator_code":
                    indicator_code,
                "year":
                    year,
                "asl":
                    asl,
            }

        for item in ranking["items"]:
            if item["asl"] == asl:
                return {
                    "status": "OK",

                    "model":
                        self.MODEL_NAME,

                    "model_version":
                        self.MODEL_VERSION,

                    "indicator_code":
                        indicator_code,

                    "year":
                        year,

                    **item,
                }

        return {
            "status": "NO_DATA",
            "indicator_code":
                indicator_code,
            "year":
                year,
            "asl":
                asl,
        }

    # =========================================================
    # Explainability
    # =========================================================

    def explain_priority(
        self,
        *,
        indicator_code: str,
        year: int,
        asl: str,
    ) -> dict:
        """
        Explain the territorial priority result.

        The explanation exposes:

            - health burden
            - health percentile
            - environmental variables
            - pollutant percentiles
            - environmental percentile
            - component weights
            - data quality context
            - final score and ranking
        """

        dataset = (
            self.build_priority_dataset(
                indicator_code=indicator_code,
                year=year,
            )
        )

        if dataset.empty:
            return {
                "status": "NO_DATA",
                "indicator_code":
                    indicator_code,
                "year":
                    year,
                "asl":
                    asl,
            }

        selected = dataset[
            dataset["asl"] == asl
        ]

        if selected.empty:
            return {
                "status": "NO_DATA",
                "indicator_code":
                    indicator_code,
                "year":
                    year,
                "asl":
                    asl,
            }

        row = selected.iloc[0]

        # -----------------------------------------------------
        # Environmental explanation
        # -----------------------------------------------------

        pollutant_details = []

        for column in ENVIRONMENTAL_COLUMNS:
            if column not in dataset.columns:
                continue

            percentile_column = (
                f"{column}_percentile"
            )

            value = row[column]

            percentile = None

            if (
                percentile_column
                in dataset.columns
            ):
                percentile = row[
                    percentile_column
                ]

            pollutant_details.append(
                {
                    "variable":
                        column,

                    "value":
                        (
                            None
                            if pd.isna(value)
                            else round(
                                float(value),
                                4,
                            )
                        ),

                    "relative_percentile":
                        (
                            None
                            if (
                                percentile is None
                                or pd.isna(
                                    percentile
                                )
                            )
                            else round(
                                float(
                                    percentile
                                ),
                                4,
                            )
                        ),
                }
            )

        # -----------------------------------------------------
        # Data quality context
        # -----------------------------------------------------

        quality = {}

        quality_columns = [
            "integration_quality_status",
            "meteo_quality_status",
            "meteo_available",
            "meteo_year_coverage_percent",
        ]

        for column in quality_columns:
            if column not in dataset.columns:
                continue

            value = row[column]

            if pd.isna(value):
                value = None

            elif hasattr(
                value,
                "item",
            ):
                value = value.item()

            quality[column] = value

        # -----------------------------------------------------
        # Health values
        # -----------------------------------------------------

        health_percentile = row[
            "health_percentile"
        ]

        environment_percentile = row[
            "environment_percentile"
        ]

        priority_score = row[
            "priority_score"
        ]

        priority_rank = row[
            "priority_rank"
        ]

        return {
            "status": "OK",

            "model":
                self.MODEL_NAME,

            "model_version":
                self.MODEL_VERSION,

            "indicator_code":
                indicator_code,

            "year":
                year,

            "asl":
                asl,

            "priority_rank":
                (
                    None
                    if pd.isna(
                        priority_rank
                    )
                    else int(
                        priority_rank
                    )
                ),

            "priority_level":
                row[
                    "priority_level"
                ],

            "priority_score":
                (
                    None
                    if pd.isna(
                        priority_score
                    )
                    else round(
                        float(
                            priority_score
                        ),
                        2,
                    )
                ),

            "health_component": {
                "prevalence_per_1000":
                    (
                        None
                        if pd.isna(
                            row[
                                "prevalence_per_1000"
                            ]
                        )
                        else round(
                            float(
                                row[
                                    "prevalence_per_1000"
                                ]
                            ),
                            4,
                        )
                    ),

                "relative_percentile":
                    (
                        None
                        if pd.isna(
                            health_percentile
                        )
                        else round(
                            float(
                                health_percentile
                            ),
                            4,
                        )
                    ),

                "weight":
                    self.HEALTH_WEIGHT,
            },

            "environment_component": {
                "relative_percentile":
                    (
                        None
                        if pd.isna(
                            environment_percentile
                        )
                        else round(
                            float(
                                environment_percentile
                            ),
                            4,
                        )
                    ),

                "weight":
                    self.ENVIRONMENT_WEIGHT,

                "variables":
                    pollutant_details,
            },

            "data_quality":
                quality,

            "explanation": (
                "The priority score combines "
                "relative health burden and "
                "relative environmental burden "
                f"using weights of {self.HEALTH_WEIGHT:.0%} for health and "
                f"{self.ENVIRONMENT_WEIGHT:.0%} for the environment. "
                "The result is a comparative "
                "decision-support indicator, not "
                "a causal estimate or clinical "
                "prediction."
            ),
        }

    # =========================================================
    # Model card
    # =========================================================

    def get_model_card(
        self,
    ) -> dict:
        """
        Return methodological metadata for the current
        explainable decision-support model.
        """

        return {
            "model":
                self.MODEL_NAME,

            "version":
                self.MODEL_VERSION,

            "type":
                "EXPLAINABLE_RULE_BASED_SCORING",

            "purpose": (
                "Territorial prioritization for "
                "One Health decision support."
            ),

            "unit_of_analysis":
                "ASL_YEAR_INDICATOR",

            "health_component":
                (
                    "prevalence_per_1000 "
                    "relative percentile"
                ),

            "environment_component":
                (
                    "mean relative percentile "
                    "of available NO2, O3, "
                    "PM10 and PM2.5 annual "
                    "mean concentrations"
                ),

            "score_definition": (
                "100 * (health_weight * "
                "health_percentile + "
                "environment_weight * "
                "environment_percentile)"
            ),

            "weights": {
                "health":
                    self.HEALTH_WEIGHT,

                "environment":
                    self.ENVIRONMENT_WEIGHT,
            },

            "missing_data_policy": (
                "Missing environmental and "
                "meteorological values are not "
                "converted to zero. A composite "
                "priority score is produced only "
                "when both health and environmental "
                "components are available."
            ),

            "priority_levels": {
                "HIGH":
                    "top relative third",

                "MEDIUM":
                    "middle relative third",

                "LOW":
                    "bottom relative third",

                "UNDEFINED":
                    (
                        "priority score cannot "
                        "be calculated"
                    ),
            },

            "limitations": [
                (
                    "The score is relative and "
                    "depends on the territories "
                    "included in the comparison."
                ),
                (
                    "The score does not establish "
                    "causal relationships."
                ),
                (
                    "It must not be interpreted "
                    "as an individual clinical "
                    "risk prediction."
                ),
                (
                    "Environmental exposures are "
                    "ecological ASL-year measures."
                ),
                (
                    "Equal component weights are "
                    "a transparent methodological "
                    "choice and do not represent "
                    "estimated causal effects."
                ),
                (
                    "Data quality and meteorological "
                    "coverage must be evaluated "
                    "alongside the priority score."
                ),
            ],
        }