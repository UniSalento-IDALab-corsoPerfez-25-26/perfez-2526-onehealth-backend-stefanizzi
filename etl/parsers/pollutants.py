from pathlib import Path

import pandas as pd

from etl.profilers.csv_profiler import read_arpa_csv


COLUMN_MAPPING = {
    "id_pollutant": "source_pollutant_id",
    "sigla": "code",
    "descrizione": "description",
    "periodo_di_misurazione": "measurement_period",
    "valore_limite": "source_limit",
    "soglia_di_allarme": "alert_threshold",
    "unita_misura": "unit",
    "eionet_concept_uri": "eionet_uri",
}


def parse_pollutants(path: Path) -> pd.DataFrame:
    frame = read_arpa_csv(path)

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

    for column in [
        "source_limit",
        "alert_threshold",
    ]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(
                frame[column],
                errors="coerce",
            )

    if "code" in frame.columns:
        frame["code"] = (
            frame["code"]
            .astype("string")
            .str.strip()
            .str.upper()
        )

    frame["source"] = "ARPAP"

    return frame