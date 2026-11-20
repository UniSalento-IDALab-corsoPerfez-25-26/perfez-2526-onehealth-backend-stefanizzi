from pathlib import Path

import pandas as pd


def age_to_group(age: int) -> str | None:
    """
    Converte l'età puntuale nelle classi utilizzate
    dai dataset sanitari AReSS.
    """

    if 40 <= age <= 44:
        return "40-44"

    if 45 <= age <= 49:
        return "45-49"

    if 50 <= age <= 54:
        return "50-54"

    if 55 <= age <= 59:
        return "55-59"

    if 60 <= age <= 64:
        return "60-64"

    if 65 <= age <= 69:
        return "65-69"

    if 70 <= age <= 74:
        return "70-74"

    if 75 <= age <= 79:
        return "75-79"

    if 80 <= age <= 84:
        return "80-84"

    if 85 <= age <= 110:
        return "85+"

    return None


def parse_istat_population(
    path: Path,
    *,
    year: int,
) -> pd.DataFrame:

    frame = pd.read_csv(
        path,
        sep=";",
        skiprows=1,
        dtype={
            "Codice comune": "string",
        },
    )

    required = {
        "Codice comune",
        "Comune",
        "Età",
        "Totale maschi",
        "Totale femmine",
        "Totale",
    }

    missing = required - set(frame.columns)

    if missing:
        raise ValueError(
            f"Colonne ISTAT mancanti: {sorted(missing)}"
        )

    frame = frame[
        [
            "Codice comune",
            "Comune",
            "Età",
            "Totale maschi",
            "Totale femmine",
            "Totale",
        ]
    ].copy()

    frame = frame.rename(
        columns={
            "Codice comune": "municipality_code",
            "Comune": "municipality",
            "Età": "age",
            "Totale maschi": "M",
            "Totale femmine": "F",
            "Totale": "ALL",
        }
    )

    frame["municipality_code"] = (
        frame["municipality_code"]
        .astype("string")
        .str.strip()
        .str.zfill(6)
    )

    frame["municipality"] = (
        frame["municipality"]
        .astype("string")
        .str.strip()
    )

    frame["age"] = pd.to_numeric(
        frame["age"],
        errors="coerce",
    )

    for column in ["M", "F", "ALL"]:
        frame[column] = pd.to_numeric(
            frame[column],
            errors="coerce",
        )

    # Eliminiamo eventuali righe non interpretabili come età.
    frame = frame[
        frame["age"].notna()
    ].copy()

    frame["age"] = frame["age"].astype(int)

    # Elimina i codici speciali ISTAT (es. 999 = Totale)
    frame = frame[
        frame["age"].between(0, 110)
    ].copy()

    frame["year"] = year

    # Il codice provincia coincide con i primi 3 caratteri
    # del codice ISTAT comunale.
    frame["province_code"] = (
        frame["municipality_code"]
        .str[:3]
    )

    # Formato long: M / F / ALL
    frame = frame.melt(
        id_vars=[
            "year",
            "province_code",
            "municipality_code",
            "municipality",
            "age",
        ],
        value_vars=[
            "M",
            "F",
            "ALL",
        ],
        var_name="sex",
        value_name="population",
    )

    frame["population"] = (
        frame["population"]
        .astype("Int64")
    )

    frame["age_group"] = (
        frame["age"]
        .apply(age_to_group)
    )

    frame["source"] = "ISTAT"

    return frame[
        [
            "year",
            "province_code",
            "municipality_code",
            "municipality",
            "sex",
            "age",
            "age_group",
            "population",
            "source",
        ]
    ]