from pathlib import Path

import pandas as pd


AGE_MAPPING = {
    "85 e oltre": "85+",
    ">=85": "85+",
}

SEX_MAPPING = {
    "Femmine": "F",
    "Maschi": "M",
    "Tutti": "ALL",
}


def parse_chronic_indicator(
    path: Path,
    *,
    indicator_code: str,
    indicator_name: str,
) -> pd.DataFrame:
    frame = pd.read_csv(path)

    frame.columns = [
        str(column).strip().lower()
        for column in frame.columns
    ]

    required = {
        "asl",
        "anno",
        "sesso",
        "eta",
        "numero",
    }

    missing = required - set(frame.columns)

    if missing:
        raise ValueError(
            f"Colonne mancanti: {sorted(missing)}"
        )

    frame = frame.rename(
        columns={
            "asl": "geographic_area",
            "anno": "year",
            "sesso": "sex",
            "eta": "age_group",
            "numero": "cases",
        }
    )

    frame["year"] = pd.to_numeric(
        frame["year"],
        errors="coerce",
    ).astype("Int64")

    frame["cases"] = pd.to_numeric(
        frame["cases"],
        errors="coerce",
    ).astype("Int64")

    frame["geographic_area"] = (
        frame["geographic_area"]
        .astype("string")
        .str.strip()
    )

    frame["sex"] = (
        frame["sex"]
        .astype("string")
        .str.strip()
        .replace(SEX_MAPPING)
    )

    frame["age_group"] = (
        frame["age_group"]
        .astype("string")
        .str.strip()
        .replace(AGE_MAPPING)
    )

    frame["geographic_level"] = "ASL"

    frame.loc[
        frame["geographic_area"].str.upper() == "PUGLIA",
        "geographic_level",
    ] = "REGION"

    frame["indicator_code"] = indicator_code
    frame["indicator_name"] = indicator_name
    frame["source"] = "ARESS"

    return frame[
        [
            "indicator_code",
            "indicator_name",
            "year",
            "geographic_level",
            "geographic_area",
            "sex",
            "age_group",
            "cases",
            "source",
        ]
    ]


def parse_bpco(path: Path) -> pd.DataFrame:
    return parse_chronic_indicator(
        path,
        indicator_code="BPCO",
        indicator_name="Broncopneumopatia cronica ostruttiva",
    )