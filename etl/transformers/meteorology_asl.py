from __future__ import annotations

from pathlib import Path

import pandas as pd


STATION_TO_ASL = {
    "bari": "Bari",
    "brindisi": "Brindisi",
    "foggia": "Foggia",
    "lecce": "Lecce",
    "taranto": "Taranto",
}


def _normalize_station_name(
    value: object,
) -> str:
    """
    Normalizza il nome della stazione per il mapping
    verso la ASL territoriale.
    """

    if pd.isna(value):
        return ""

    return (
        str(value)
        .strip()
        .lower()
    )


def _meteorology_quality(
    coverage_percent: float,
) -> str:
    """
    Classifica la copertura temporale annuale.

    >= 90%  -> VALID
    >= 60%  -> PARTIAL_COVERAGE
    < 60%   -> LOW_COVERAGE
    """

    if pd.isna(coverage_percent):
        return "NO_DATA"

    if coverage_percent >= 90:
        return "VALID"

    if coverage_percent >= 60:
        return "PARTIAL_COVERAGE"

    return "LOW_COVERAGE"


def _expected_days_in_year(
    year: int,
) -> int:
    """
    Restituisce 365 o 366 in base all'anno.
    """

    return int(
        pd.Timestamp(
            year=year,
            month=12,
            day=31,
        ).dayofyear
    )


def build_meteorology_asl_year(
    daily_path: Path,
    output_path: Path,
    *,
    year: int,
) -> pd.DataFrame:
    """
    Aggrega il dataset meteorologico giornaliero ARPAP
    al livello ASL × anno.

    Principi metodologici:
    - nessuna imputazione temporale;
    - nessuna stima dei giorni mancanti;
    - vengono aggregate solo le variabili realmente presenti;
    - gli indicatori derivati vengono prodotti solo se
      la variabile sorgente è disponibile;
    - la copertura annuale viene sempre esplicitata;
    - i valori prodotti rappresentano il periodo osservato,
      non necessariamente l'intero anno.
    """

    # ---------------------------------------------------------
    # Controlli iniziali
    # ---------------------------------------------------------

    if not daily_path.exists():
        raise FileNotFoundError(
            "Dataset meteorologico giornaliero "
            f"non trovato: {daily_path}"
        )

    frame = pd.read_parquet(
        daily_path
    )

    if frame.empty:
        raise ValueError(
            "Il dataset meteorologico giornaliero è vuoto."
        )

    required_columns = {
        "station_name",
        "measurement_date",
        "coverage_percent",
    }

    missing_columns = (
        required_columns
        - set(frame.columns)
    )

    if missing_columns:
        raise ValueError(
            "Colonne meteorologiche minime mancanti: "
            f"{sorted(missing_columns)}"
        )

    frame = frame.copy()

    # ---------------------------------------------------------
    # Normalizzazione temporale
    # ---------------------------------------------------------

    frame["measurement_date"] = pd.to_datetime(
        frame["measurement_date"],
        errors="coerce",
    )

    invalid_dates = frame[
        frame["measurement_date"].isna()
    ]

    if not invalid_dates.empty:
        raise ValueError(
            "Sono presenti record meteorologici "
            "con measurement_date non valida."
        )

    frame["year"] = (
        frame["measurement_date"]
        .dt.year
        .astype("Int64")
    )

    frame = frame[
        frame["year"] == year
    ].copy()

    if frame.empty:
        raise ValueError(
            f"Nessun dato meteorologico trovato "
            f"per l'anno {year}."
        )

    # ---------------------------------------------------------
    # Mapping stazione -> ASL
    # ---------------------------------------------------------

    frame["station_key"] = (
        frame["station_name"]
        .apply(_normalize_station_name)
    )

    frame["asl"] = (
        frame["station_key"]
        .map(STATION_TO_ASL)
    )

    unresolved = frame[
        frame["asl"].isna()
    ]

    if not unresolved.empty:
        station_names = sorted(
            unresolved["station_name"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        raise ValueError(
            "Stazioni meteorologiche senza mapping ASL: "
            f"{station_names}"
        )

    # ---------------------------------------------------------
    # Normalizzazione numerica minima
    # ---------------------------------------------------------

    frame["coverage_percent"] = pd.to_numeric(
        frame["coverage_percent"],
        errors="coerce",
    )

    # ---------------------------------------------------------
    # Specifica dinamica delle aggregazioni
    # ---------------------------------------------------------

    aggregation_spec: dict[
        str,
        tuple[str, str],
    ] = {
        "meteo_days_available": (
            "measurement_date",
            "nunique",
        ),
        "meteo_mean_daily_coverage": (
            "coverage_percent",
            "mean",
        ),
    }

    # Temperatura
    if "temperature_mean" in frame.columns:
        aggregation_spec[
            "meteo_temperature_mean_observed"
        ] = (
            "temperature_mean",
            "mean",
        )

    if "temperature_min" in frame.columns:
        aggregation_spec[
            "meteo_temperature_min_observed"
        ] = (
            "temperature_min",
            "min",
        )

    if "temperature_max" in frame.columns:
        aggregation_spec[
            "meteo_temperature_max_observed"
        ] = (
            "temperature_max",
            "max",
        )

    # Umidità
    if "relative_humidity_mean" in frame.columns:
        aggregation_spec[
            "meteo_relative_humidity_mean_observed"
        ] = (
            "relative_humidity_mean",
            "mean",
        )

    # Precipitazioni
    if "precipitation_total" in frame.columns:
        aggregation_spec[
            "meteo_precipitation_total_observed"
        ] = (
            "precipitation_total",
            "sum",
        )

    # Vento
    if "wind_speed_mean" in frame.columns:
        aggregation_spec[
            "meteo_wind_speed_mean_observed"
        ] = (
            "wind_speed_mean",
            "mean",
        )

    if "wind_speed_max" in frame.columns:
        aggregation_spec[
            "meteo_wind_speed_max_observed"
        ] = (
            "wind_speed_max",
            "max",
        )

    # Radiazione solare
    if "solar_radiation_mean" in frame.columns:
        aggregation_spec[
            "meteo_solar_radiation_mean_observed"
        ] = (
            "solar_radiation_mean",
            "mean",
        )

    # Pressione atmosferica
    if "atmospheric_pressure_mean" in frame.columns:
        aggregation_spec[
            "meteo_atmospheric_pressure_mean_observed"
        ] = (
            "atmospheric_pressure_mean",
            "mean",
        )

    # ---------------------------------------------------------
    # Aggregazione principale ASL × anno
    # ---------------------------------------------------------

    annual = (
        frame.groupby(
            [
                "year",
                "asl",
            ],
            as_index=False,
        )
        .agg(**aggregation_spec)
    )

    # ---------------------------------------------------------
    # Indicatori derivati
    # ---------------------------------------------------------
    #
    # Vengono creati solo se esiste la variabile fisica
    # sorgente. In questo modo l'assenza della temperatura
    # non viene erroneamente interpretata come zero giorni
    # caldi/freddi.
    # ---------------------------------------------------------

    if (
        "rain_day" in frame.columns
        and "precipitation_total" in frame.columns
    ):
        rain_days = (
            frame.groupby(
                [
                    "year",
                    "asl",
                ],
                as_index=False,
            )["rain_day"]
            .sum()
            .rename(
                columns={
                    "rain_day":
                        "meteo_rain_days_observed",
                }
            )
        )

        annual = annual.merge(
            rain_days,
            on=[
                "year",
                "asl",
            ],
            how="left",
            validate="one_to_one",
        )

    if (
        "hot_day_30" in frame.columns
        and "temperature_max" in frame.columns
    ):
        hot_days_30 = (
            frame.groupby(
                [
                    "year",
                    "asl",
                ],
                as_index=False,
            )["hot_day_30"]
            .sum()
            .rename(
                columns={
                    "hot_day_30":
                        "meteo_hot_days_over_30_observed",
                }
            )
        )

        annual = annual.merge(
            hot_days_30,
            on=[
                "year",
                "asl",
            ],
            how="left",
            validate="one_to_one",
        )

    if (
        "hot_day_35" in frame.columns
        and "temperature_max" in frame.columns
    ):
        hot_days_35 = (
            frame.groupby(
                [
                    "year",
                    "asl",
                ],
                as_index=False,
            )["hot_day_35"]
            .sum()
            .rename(
                columns={
                    "hot_day_35":
                        "meteo_hot_days_over_35_observed",
                }
            )
        )

        annual = annual.merge(
            hot_days_35,
            on=[
                "year",
                "asl",
            ],
            how="left",
            validate="one_to_one",
        )

    if (
        "frost_day" in frame.columns
        and "temperature_min" in frame.columns
    ):
        frost_days = (
            frame.groupby(
                [
                    "year",
                    "asl",
                ],
                as_index=False,
            )["frost_day"]
            .sum()
            .rename(
                columns={
                    "frost_day":
                        "meteo_frost_days_observed",
                }
            )
        )

        annual = annual.merge(
            frost_days,
            on=[
                "year",
                "asl",
            ],
            how="left",
            validate="one_to_one",
        )

    # ---------------------------------------------------------
    # Copertura annuale
    # ---------------------------------------------------------

    expected_days = (
        _expected_days_in_year(
            year
        )
    )

    annual[
        "meteo_expected_days"
    ] = expected_days

    annual[
        "meteo_year_coverage_percent"
    ] = (
        annual[
            "meteo_days_available"
        ]
        / annual[
            "meteo_expected_days"
        ]
        * 100
    ).round(2)

    annual[
        "meteo_quality_status"
    ] = annual[
        "meteo_year_coverage_percent"
    ].apply(
        _meteorology_quality
    )

    # ---------------------------------------------------------
    # Variabili realmente disponibili
    # ---------------------------------------------------------

    available_variables: list[str] = []

    if "temperature_mean" in frame.columns:
        available_variables.append(
            "temperature"
        )

    if "relative_humidity_mean" in frame.columns:
        available_variables.append(
            "relative_humidity"
        )

    if "precipitation_total" in frame.columns:
        available_variables.append(
            "precipitation"
        )

    if "wind_speed_mean" in frame.columns:
        available_variables.append(
            "wind"
        )

    if "solar_radiation_mean" in frame.columns:
        available_variables.append(
            "solar_radiation"
        )

    if "atmospheric_pressure_mean" in frame.columns:
        available_variables.append(
            "atmospheric_pressure"
        )

    annual[
        "meteo_available_variables"
    ] = ",".join(
        available_variables
    )

    annual[
        "meteo_variable_count"
    ] = len(
        available_variables
    )

    # ---------------------------------------------------------
    # Metadati
    # ---------------------------------------------------------

    annual[
        "meteo_source"
    ] = "ARPAP"

    annual[
        "meteo_network"
    ] = "METEO_STANDARD"

    annual[
        "meteo_period_type"
    ] = "OBSERVED_PERIOD"

    annual[
        "meteo_is_full_year"
    ] = (
        annual[
            "meteo_days_available"
        ]
        >= annual[
            "meteo_expected_days"
        ]
    )

    # ---------------------------------------------------------
    # Arrotondamenti
    # ---------------------------------------------------------

    numeric_columns = [
        column
        for column in annual.columns
        if (
            column.startswith("meteo_")
            and pd.api.types.is_numeric_dtype(
                annual[column]
            )
        )
    ]

    for column in numeric_columns:
        annual[column] = (
            annual[column]
            .round(4)
        )

    # ---------------------------------------------------------
    # Controlli logici
    # ---------------------------------------------------------

    duplicate_mask = annual.duplicated(
        subset=[
            "year",
            "asl",
        ],
        keep=False,
    )

    if duplicate_mask.any():
        duplicate_rows = annual.loc[
            duplicate_mask,
            [
                "year",
                "asl",
            ],
        ]

        raise ValueError(
            "Il dataset meteorologico ASL contiene "
            "chiavi anno-ASL duplicate.\n"
            f"{duplicate_rows.to_string(index=False)}"
        )

    if (
        annual[
            "meteo_days_available"
        ]
        > annual[
            "meteo_expected_days"
        ]
    ).any():
        raise ValueError(
            "Sono presenti ASL con un numero di giorni "
            "meteorologici superiore ai giorni dell'anno."
        )

    # ---------------------------------------------------------
    # Ordinamento
    # ---------------------------------------------------------

    preferred_columns = [
        "year",
        "asl",
        "meteo_days_available",
        "meteo_expected_days",
        "meteo_year_coverage_percent",
        "meteo_mean_daily_coverage",
        "meteo_quality_status",
        "meteo_is_full_year",
        "meteo_available_variables",
        "meteo_variable_count",
        "meteo_temperature_mean_observed",
        "meteo_temperature_min_observed",
        "meteo_temperature_max_observed",
        "meteo_relative_humidity_mean_observed",
        "meteo_precipitation_total_observed",
        "meteo_rain_days_observed",
        "meteo_wind_speed_mean_observed",
        "meteo_wind_speed_max_observed",
        "meteo_solar_radiation_mean_observed",
        "meteo_atmospheric_pressure_mean_observed",
        "meteo_hot_days_over_30_observed",
        "meteo_hot_days_over_35_observed",
        "meteo_frost_days_observed",
        "meteo_period_type",
        "meteo_source",
        "meteo_network",
    ]

    existing_preferred_columns = [
        column
        for column in preferred_columns
        if column in annual.columns
    ]

    remaining_columns = [
        column
        for column in annual.columns
        if column
        not in existing_preferred_columns
    ]

    annual = annual[
        existing_preferred_columns
        + remaining_columns
    ]

    annual = (
        annual
        .sort_values(
            [
                "year",
                "asl",
            ]
        )
        .reset_index(drop=True)
    )

    # ---------------------------------------------------------
    # Scrittura
    # ---------------------------------------------------------

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    annual.to_parquet(
        output_path,
        index=False,
    )

    # ---------------------------------------------------------
    # Riepilogo
    # ---------------------------------------------------------

    print("=" * 70)
    print("METEOROLOGIA ASL × ANNO")
    print("=" * 70)

    print(
        "Record:",
        len(annual),
    )

    print(
        "Anno:",
        year,
    )

    print(
        "ASL:",
        sorted(
            annual["asl"]
            .astype(str)
            .unique()
            .tolist()
        ),
    )

    print(
        "Variabili disponibili:",
        ", ".join(available_variables)
        if available_variables
        else "nessuna",
    )

    print()

    summary_columns = [
        "year",
        "asl",
        "meteo_days_available",
        "meteo_expected_days",
        "meteo_year_coverage_percent",
        "meteo_mean_daily_coverage",
        "meteo_quality_status",
        "meteo_is_full_year",
        "meteo_available_variables",
    ]

    print(
        annual[
            summary_columns
        ].to_string(
            index=False
        )
    )

    print()

    print(
        "File creato:",
        output_path,
    )

    return annual