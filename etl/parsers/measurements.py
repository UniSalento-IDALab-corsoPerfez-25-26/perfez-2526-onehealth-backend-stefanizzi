from pathlib import Path

import pandas as pd

from etl.profilers.csv_profiler import read_arpa_csv


COLUMN_MAPPING = {
    "data_di_misurazione": "measurement_date",
    "id_station": "source_station_id",
    "denominazione": "station_name",
    "comune": "municipality",
    "provincia": "province",
    "longitude": "longitude",
    "latitude": "latitude",
    "tipologia_di_area": "tipologia_di_area",
    "tipologia_di_stazione": "tipologia_di_stazione",
    "rete": "network",
    "interesse_rete": "interesse_rete",
    "inquinante_misurato": "pollutant_code",
    "valore_inquinante_misurato": "value",
    "unita_misura": "unit",
    "limite": "source_limit",
    "superamenti": "source_exceedances_ytd",
    "indice_qualita": "source_quality_index",
    "classe_qualita": "source_quality_class",
}


def parse_measurements(path: Path) -> pd.DataFrame:
    frame = read_arpa_csv(path)

    # Normalizzazione nomi colonne.
    # Ad esempio Longitude -> longitude.
    frame.columns = [
        str(column).strip().lower().replace(" ", "_")
        for column in frame.columns
    ]

    mapping = {
        source: target
        for source, target in COLUMN_MAPPING.items()
        if source in frame.columns
    }

    frame = frame.rename(columns=mapping)

    # -----------------------------------------------------
    # Data
    # -----------------------------------------------------

    if "measurement_date" not in frame.columns:
        raise ValueError(
            "La colonna measurement_date non è presente "
            "nel dataset ARPA."
        )

    # ARPA usa il formato ISO YYYY-MM-DD.
    frame["measurement_date"] = pd.to_datetime(
        frame["measurement_date"],
        format="%Y-%m-%d",
        errors="coerce",
    )

    invalid_dates = frame["measurement_date"].isna()

    if invalid_dates.any():
        raise ValueError(
            f"Trovate {int(invalid_dates.sum())} righe "
            "con data_di_misurazione non valida."
        )

    # -----------------------------------------------------
    # Valore della misura
    # -----------------------------------------------------

    if "value" in frame.columns:
        frame["value"] = pd.to_numeric(
            frame["value"],
            errors="coerce",
        )

    # -----------------------------------------------------
    # Altri campi numerici
    # -----------------------------------------------------

    numeric_columns = [
        "longitude",
        "latitude",
        "source_limit",
        "source_exceedances_ytd",
        "source_quality_index",
    ]

    for column in numeric_columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(
                frame[column],
                errors="coerce",
            )

    # -----------------------------------------------------
    # Normalizzazione stringhe principali
    # -----------------------------------------------------

    if "source_station_id" in frame.columns:
        frame["source_station_id"] = (
            frame["source_station_id"]
            .astype("string")
            .str.strip()
        )

    if "pollutant_code" in frame.columns:
        frame["pollutant_code"] = (
            frame["pollutant_code"]
            .astype("string")
            .str.strip()
            .str.upper()
        )

    if "network" in frame.columns:
        frame["network"] = (
            frame["network"]
            .astype("string")
            .str.strip()
            .str.upper()
        )

    frame["source"] = "ARPAP"

    return frame