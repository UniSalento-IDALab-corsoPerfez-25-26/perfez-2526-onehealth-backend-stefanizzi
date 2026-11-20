from __future__ import annotations

from pathlib import Path

import pandas as pd


def build_daily_meteorology(
    hourly_path: Path,
    output_path: Path,
) -> pd.DataFrame:
    """
    Aggrega le osservazioni meteorologiche sub-orarie/orarie
    a livello giornaliero per stazione.

    La frequenza attesa viene inferita automaticamente
    dalla serie temporale della stazione.
    """

    if not hourly_path.exists():
        raise FileNotFoundError(
            f"Dataset meteorologico non trovato: {hourly_path}"
        )

    frame = pd.read_parquet(hourly_path)

    if frame.empty:
        raise ValueError(
            "Il dataset meteorologico è vuoto."
        )

    required_columns = {
        "source_station_id",
        "station_name",
        "measurement_datetime",
        "measurement_date",
        "latitude",
        "longitude",
    }

    missing = required_columns - set(frame.columns)

    if missing:
        raise ValueError(
            "Colonne meteorologiche mancanti: "
            f"{sorted(missing)}"
        )

    frame["measurement_datetime"] = pd.to_datetime(
        frame["measurement_datetime"],
        errors="coerce",
    )

    frame = frame[
        frame["measurement_datetime"].notna()
    ].copy()

    frame["measurement_date"] = (
        frame["measurement_datetime"]
        .dt.date
    )

    # ---------------------------------------------------------
    # Inferenza della frequenza per stazione
    # ---------------------------------------------------------

    station_frequency: dict[str, float] = {}

    for station_id, group in frame.groupby(
        "source_station_id"
    ):
        timestamps = (
            group["measurement_datetime"]
            .drop_duplicates()
            .sort_values()
        )

        differences = (
            timestamps.diff()
            .dropna()
        )

        # Consideriamo intervalli ragionevoli <= 3 ore
        # per evitare che i buchi influenzino la mediana.
        differences = differences[
            (differences > pd.Timedelta(0))
            & (
                differences
                <= pd.Timedelta(hours=3)
            )
        ]

        if differences.empty:
            raise ValueError(
                "Impossibile determinare la frequenza "
                f"della stazione {station_id}."
            )

        interval_minutes = (
            differences
            .dt.total_seconds()
            .median()
            / 60
        )

        if interval_minutes <= 0:
            raise ValueError(
                "Frequenza non valida per la stazione "
                f"{station_id}: {interval_minutes}"
            )

        station_frequency[
            str(station_id)
        ] = float(interval_minutes)

    # ---------------------------------------------------------
    # Copertura giornaliera
    # ---------------------------------------------------------

    daily_coverage = (
        frame.groupby(
            [
                "source_station_id",
                "station_name",
                "measurement_date",
                "latitude",
                "longitude",
            ],
            as_index=False,
        )
        .agg(
            observation_count=(
                "measurement_datetime",
                "count",
            ),
            distinct_observations=(
                "measurement_datetime",
                "nunique",
            ),
        )
    )

    daily_coverage[
        "sampling_interval_minutes"
    ] = (
        daily_coverage[
            "source_station_id"
        ]
        .astype(str)
        .map(station_frequency)
    )

    daily_coverage[
        "expected_observations"
    ] = (
        1440
        / daily_coverage[
            "sampling_interval_minutes"
        ]
    ).round().astype("Int64")

    daily_coverage[
        "coverage_percent"
    ] = (
        daily_coverage[
            "distinct_observations"
        ]
        / daily_coverage[
            "expected_observations"
        ]
        * 100
    ).round(2)

    # Non permettiamo valori >100 dovuti a peculiarità
    # dell'ora solare o della sorgente.
    daily_coverage[
        "coverage_percent"
    ] = (
        daily_coverage[
            "coverage_percent"
        ]
        .clip(upper=100)
    )

    # ---------------------------------------------------------
    # Aggregazioni meteorologiche
    # ---------------------------------------------------------

    aggregations = {}

    if "temperature" in frame.columns:
        aggregations.update(
            {
                "temperature_mean": (
                    "temperature",
                    "mean",
                ),
                "temperature_min": (
                    "temperature",
                    "min",
                ),
                "temperature_max": (
                    "temperature",
                    "max",
                ),
            }
        )

    if "relative_humidity" in frame.columns:
        aggregations[
            "relative_humidity_mean"
        ] = (
            "relative_humidity",
            "mean",
        )

    if "precipitation" in frame.columns:
        aggregations[
            "precipitation_total"
        ] = (
            "precipitation",
            "sum",
        )

    if "wind_speed" in frame.columns:
        aggregations.update(
            {
                "wind_speed_mean": (
                    "wind_speed",
                    "mean",
                ),
                "wind_speed_max": (
                    "wind_speed",
                    "max",
                ),
            }
        )

    if "solar_radiation" in frame.columns:
        aggregations[
            "solar_radiation_mean"
        ] = (
            "solar_radiation",
            "mean",
        )

    if "atmospheric_pressure" in frame.columns:
        aggregations[
            "atmospheric_pressure_mean"
        ] = (
            "atmospheric_pressure",
            "mean",
        )

    daily = (
        frame.groupby(
            [
                "source_station_id",
                "station_name",
                "measurement_date",
                "latitude",
                "longitude",
            ],
            as_index=False,
        )
        .agg(**aggregations)
    )

    daily = daily.merge(
        daily_coverage,
        on=[
            "source_station_id",
            "station_name",
            "measurement_date",
            "latitude",
            "longitude",
        ],
        how="left",
        validate="one_to_one",
    )

    # ---------------------------------------------------------
    # Variabili temporali
    # ---------------------------------------------------------

    date_series = pd.to_datetime(
        daily["measurement_date"]
    )

    daily["year"] = (
        date_series.dt.year
        .astype("Int64")
    )

    daily["month"] = (
        date_series.dt.month
        .astype("Int64")
    )

    # ---------------------------------------------------------
    # Indicatori giornalieri
    # ---------------------------------------------------------

    daily["rain_day"] = False

    if "precipitation_total" in daily.columns:
        daily["rain_day"] = (
            daily["precipitation_total"] > 0
        )

    daily["hot_day_30"] = False
    daily["hot_day_35"] = False
    daily["frost_day"] = False

    if "temperature_max" in daily.columns:
        daily["hot_day_30"] = (
            daily["temperature_max"] > 30
        )

        daily["hot_day_35"] = (
            daily["temperature_max"] > 35
        )

    if "temperature_min" in daily.columns:
        daily["frost_day"] = (
            daily["temperature_min"] < 0
        )

    # ---------------------------------------------------------
    # Qualità giornaliera
    # ---------------------------------------------------------

    daily["quality_status"] = "VALID"

    daily.loc[
        daily["coverage_percent"] < 75,
        "quality_status",
    ] = "VALID_WITH_WARNING"

    daily.loc[
        daily["coverage_percent"] < 50,
        "quality_status",
    ] = "LOW_COVERAGE"

    # ---------------------------------------------------------
    # Arrotondamenti
    # ---------------------------------------------------------

    numeric_columns = [
        "temperature_mean",
        "temperature_min",
        "temperature_max",
        "relative_humidity_mean",
        "precipitation_total",
        "wind_speed_mean",
        "wind_speed_max",
        "solar_radiation_mean",
        "atmospheric_pressure_mean",
    ]

    for column in numeric_columns:
        if column in daily.columns:
            daily[column] = (
                pd.to_numeric(
                    daily[column],
                    errors="coerce",
                )
                .round(4)
            )

    daily["source"] = "ARPAP"

    daily = (
        daily
        .sort_values(
            [
                "source_station_id",
                "measurement_date",
            ]
        )
        .reset_index(drop=True)
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    daily.to_parquet(
        output_path,
        index=False,
    )

    print("=" * 70)
    print("METEOROLOGIA GIORNALIERA")
    print("=" * 70)

    print(
        "Record giornalieri:",
        len(daily),
    )

    print(
        "Stazioni:",
        daily["source_station_id"].nunique(),
    )

    print(
        "Prima data:",
        daily["measurement_date"].min(),
    )

    print(
        "Ultima data:",
        daily["measurement_date"].max(),
    )

    print(
        "Intervallo campionamento (min):",
        sorted(
            daily[
                "sampling_interval_minutes"
            ]
            .dropna()
            .unique()
            .tolist()
        ),
    )

    print()
    print("QUALITY STATUS")

    print(
        daily["quality_status"]
        .value_counts(dropna=False)
        .to_string()
    )

    print(
        "File creato:",
        output_path,
    )

    return daily