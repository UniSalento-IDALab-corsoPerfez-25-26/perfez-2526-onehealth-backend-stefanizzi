from __future__ import annotations

from pathlib import Path

import pandas as pd


COLUMN_MAPPING = {
    "_id": "source_record_id",
    "data_ora": "measurement_datetime",
    "id_station": "source_station_id",
    "denominazione": "station_name",
    "temperatura": "temperature",
    "cod_validazione_temperatura":
        "temperature_validation_code",
    "umidita": "relative_humidity",
    "cod_validazione_umidita_rel":
        "humidity_validation_code",
    "precipitazione": "precipitation",
    "cod_validazione_precipitazione":
        "precipitation_validation_code",
    "velocita_vento": "wind_speed",
    "cod_validazione_velocita_vento":
        "wind_speed_validation_code",
    "direzione_vento": "wind_direction",
    "cod_validazione_direzione_vento":
        "wind_direction_validation_code",
    "rad_solare_globale": "solar_radiation",
    "cod_validazione_rad_solare_globale":
        "solar_radiation_validation_code",
    "pressione_atmosferica": "atmospheric_pressure",
    "cod_validazione_pressione_atmosferica":
        "pressure_validation_code",
    "latitude": "latitude",
    "longitude": "longitude",
}


NUMERIC_COLUMNS = [
    "temperature",
    "relative_humidity",
    "precipitation",
    "wind_speed",
    "wind_direction",
    "solar_radiation",
    "atmospheric_pressure",
    "latitude",
    "longitude",
]


VALIDATION_COLUMNS = [
    "temperature_validation_code",
    "humidity_validation_code",
    "precipitation_validation_code",
    "wind_speed_validation_code",
    "wind_direction_validation_code",
    "solar_radiation_validation_code",
    "pressure_validation_code",
]


def parse_meteorological_measurements(
    path: Path,
) -> pd.DataFrame:
    """
    Normalizza una risorsa meteorologica ARPA Puglia
    precedentemente salvata in formato Parquet.

    Operazioni principali:
    - normalizzazione dei nomi delle colonne;
    - mapping verso lo schema interno;
    - conversione timestamp;
    - conversione delle variabili meteorologiche;
    - normalizzazione dei codici di validazione;
    - recupero delle coordinate mancanti usando
      le coordinate disponibili della stessa stazione;
    - costruzione delle colonne temporali derivate;
    - aggiunta dei metadati di sorgente.
    """

    # ---------------------------------------------------------
    # Controlli iniziali
    # ---------------------------------------------------------

    if not path.exists():
        raise FileNotFoundError(
            f"File meteorologico non trovato: {path}"
        )

    frame = pd.read_parquet(
        path
    )

    if frame.empty:
        raise ValueError(
            f"Il file meteorologico è vuoto: {path}"
        )

    # ---------------------------------------------------------
    # Normalizzazione nomi colonne
    # ---------------------------------------------------------

    frame.columns = [
        str(column)
        .strip()
        .lower()
        .replace(" ", "_")
        for column in frame.columns
    ]

    # ---------------------------------------------------------
    # Mapping colonne ARPAP -> schema interno
    # ---------------------------------------------------------

    mapping = {
        source: target
        for source, target in COLUMN_MAPPING.items()
        if source in frame.columns
    }

    frame = frame.rename(
        columns=mapping
    )

    # ---------------------------------------------------------
    # Verifica colonne minime
    # ---------------------------------------------------------

    required_columns = {
        "measurement_datetime",
        "source_station_id",
        "station_name",
        "latitude",
        "longitude",
    }

    missing_columns = (
        required_columns
        - set(frame.columns)
    )

    if missing_columns:
        raise ValueError(
            "Colonne meteorologiche mancanti: "
            f"{sorted(missing_columns)}"
        )

    # ---------------------------------------------------------
    # Timestamp
    # ---------------------------------------------------------

    frame["measurement_datetime"] = (
        pd.to_datetime(
            frame["measurement_datetime"],
            errors="coerce",
        )
    )

    # ---------------------------------------------------------
    # Identificativo stazione
    # ---------------------------------------------------------

    frame["source_station_id"] = (
        frame["source_station_id"]
        .astype("string")
        .str.strip()
    )

    # Eventuali stringhe vuote diventano NA.
    frame.loc[
        frame["source_station_id"] == "",
        "source_station_id",
    ] = pd.NA

    # ---------------------------------------------------------
    # Nome stazione
    # ---------------------------------------------------------

    frame["station_name"] = (
        frame["station_name"]
        .astype("string")
        .str.strip()
    )

    frame.loc[
        frame["station_name"] == "",
        "station_name",
    ] = pd.NA

    # ---------------------------------------------------------
    # Conversione variabili numeriche
    # ---------------------------------------------------------

    for column in NUMERIC_COLUMNS:
        if column not in frame.columns:
            continue

        frame[column] = pd.to_numeric(
            frame[column],
            errors="coerce",
        )

    # ---------------------------------------------------------
    # Normalizzazione codici di validazione ARPAP
    # ---------------------------------------------------------

    for column in VALIDATION_COLUMNS:
        if column not in frame.columns:
            continue

        frame[column] = (
            frame[column]
            .astype("string")
            .str.strip()
        )

        frame.loc[
            frame[column] == "",
            column,
        ] = pd.NA

    # ---------------------------------------------------------
    # Source record ID
    # ---------------------------------------------------------

    if "source_record_id" in frame.columns:
        frame["source_record_id"] = (
            pd.to_numeric(
                frame["source_record_id"],
                errors="coerce",
            )
            .astype("Int64")
        )

    # ---------------------------------------------------------
    # Recupero coordinate mancanti
    # ---------------------------------------------------------
    #
    # Le coordinate rappresentano proprietà della stazione,
    # non della singola osservazione oraria.
    #
    # Se una singola riga non contiene Latitude/Longitude,
    # recuperiamo quindi le coordinate dagli altri record
    # appartenenti allo stesso source_station_id.
    #
    # Usiamo la mediana per essere robusti ad eventuali
    # piccolissime differenze numeriche nella sorgente.
    # ---------------------------------------------------------

    valid_coordinate_mask = (
        frame["source_station_id"].notna()
        & frame["latitude"].notna()
        & frame["longitude"].notna()
        & frame["latitude"].between(
            -90,
            90,
            inclusive="both",
        )
        & frame["longitude"].between(
            -180,
            180,
            inclusive="both",
        )
    )

    station_coordinates = (
        frame.loc[
            valid_coordinate_mask,
            [
                "source_station_id",
                "latitude",
                "longitude",
            ],
        ]
        .groupby(
            "source_station_id",
            as_index=False,
        )
        .agg(
            latitude_reference=(
                "latitude",
                "median",
            ),
            longitude_reference=(
                "longitude",
                "median",
            ),
        )
    )

    frame = frame.merge(
        station_coordinates,
        on="source_station_id",
        how="left",
        validate="many_to_one",
    )

    # Consideriamo da correggere sia i valori nulli
    # sia coordinate palesemente fuori intervallo.

    invalid_latitude = (
        frame["latitude"].isna()
        | ~frame["latitude"].between(
            -90,
            90,
            inclusive="both",
        )
    )

    invalid_longitude = (
        frame["longitude"].isna()
        | ~frame["longitude"].between(
            -180,
            180,
            inclusive="both",
        )
    )

    frame.loc[
        invalid_latitude,
        "latitude",
    ] = frame.loc[
        invalid_latitude,
        "latitude_reference",
    ]

    frame.loc[
        invalid_longitude,
        "longitude",
    ] = frame.loc[
        invalid_longitude,
        "longitude_reference",
    ]

    # ---------------------------------------------------------
    # Indicatore di coordinate recuperate
    # ---------------------------------------------------------

    frame["coordinates_imputed"] = (
        invalid_latitude
        | invalid_longitude
    )

    # True soltanto quando il recupero è realmente riuscito.

    frame["coordinates_imputed"] = (
        frame["coordinates_imputed"]
        & frame["latitude"].notna()
        & frame["longitude"].notna()
    )

    frame = frame.drop(
        columns=[
            "latitude_reference",
            "longitude_reference",
        ],
    )

    # ---------------------------------------------------------
    # Colonne temporali derivate
    # ---------------------------------------------------------

    frame["measurement_date"] = (
        frame["measurement_datetime"]
        .dt.date
    )

    frame["year"] = (
        frame["measurement_datetime"]
        .dt.year
        .astype("Int64")
    )

    frame["month"] = (
        frame["measurement_datetime"]
        .dt.month
        .astype("Int64")
    )

    frame["hour"] = (
        frame["measurement_datetime"]
        .dt.hour
        .astype("Int64")
    )

    # ---------------------------------------------------------
    # Metadati
    # ---------------------------------------------------------

    frame["source"] = "ARPAP"

    frame["network"] = "RRQA_METEO"

    # ---------------------------------------------------------
    # Ordinamento colonne
    # ---------------------------------------------------------

    ordered_columns = [
        "source_record_id",
        "measurement_datetime",
        "measurement_date",
        "year",
        "month",
        "hour",
        "source_station_id",
        "station_name",
        "latitude",
        "longitude",
        "coordinates_imputed",
        "temperature",
        "temperature_validation_code",
        "relative_humidity",
        "humidity_validation_code",
        "precipitation",
        "precipitation_validation_code",
        "wind_speed",
        "wind_speed_validation_code",
        "wind_direction",
        "wind_direction_validation_code",
        "solar_radiation",
        "solar_radiation_validation_code",
        "atmospheric_pressure",
        "pressure_validation_code",
        "network",
        "source",
    ]

    existing_columns = [
        column
        for column in ordered_columns
        if column in frame.columns
    ]

    result = frame[
        existing_columns
    ].copy()

    # ---------------------------------------------------------
    # Ordinamento record
    # ---------------------------------------------------------

    result = (
        result
        .sort_values(
            [
                "source_station_id",
                "measurement_datetime",
                "source_record_id",
            ],
            na_position="last",
        )
        .reset_index(drop=True)
    )

    return result