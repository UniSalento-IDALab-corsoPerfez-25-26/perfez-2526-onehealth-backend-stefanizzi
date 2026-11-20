import pandas as pd


REQUIRED_COLUMNS = {
    "measurement_date",
    "source_station_id",
    "pollutant_code",
    "network",
}


DUPLICATE_KEY_COLUMNS = [
    "measurement_date",
    "source_station_id",
    "pollutant_code",
    "network",
]


DUPLICATE_COMPARE_COLUMNS = [
    "value",
    "unit",
    "source_limit",
    "source_exceedances_ytd",
    "source_quality_index",
    "source_quality_class",
]


def classify_duplicates(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Classifica i duplicati in:
    - DUPLICATE_IDENTICAL
    - DUPLICATE_CONFLICT

    Due record sono considerati duplicati se condividono la stessa
    chiave naturale:
        measurement_date
        source_station_id
        pollutant_code
        network

    Se tutti gli altri valori rilevanti coincidono, il duplicato
    è considerato identico; altrimenti è considerato conflittuale.
    """

    result = frame.copy()

    duplicate_mask = result.duplicated(
        subset=DUPLICATE_KEY_COLUMNS,
        keep=False,
    )

    if not duplicate_mask.any():
        return result

    duplicated_rows = result.loc[duplicate_mask]

    grouped = duplicated_rows.groupby(
        DUPLICATE_KEY_COLUMNS,
        dropna=False,
    )

    for _, indexes in grouped.groups.items():
        group = result.loc[indexes]

        existing_compare_columns = [
            column
            for column in DUPLICATE_COMPARE_COLUMNS
            if column in group.columns
        ]

        if not existing_compare_columns:
            result.loc[
                indexes,
                "quality_status",
            ] = "DUPLICATE_IDENTICAL"

            continue

        distinct_values = (
            group[existing_compare_columns]
            .fillna("<NULL>")
            .astype(str)
            .drop_duplicates()
        )

        if len(distinct_values) == 1:
            status = "DUPLICATE_IDENTICAL"
        else:
            status = "DUPLICATE_CONFLICT"

        result.loc[
            indexes,
            "quality_status",
        ] = status

    return result


def validate_measurements(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    """
    Esegue i controlli di qualità sulle misure ARPA.

    Stati possibili:
    - VALID
    - VALID_WITH_WARNING
    - REJECTED
    - DUPLICATE_IDENTICAL
    - DUPLICATE_CONFLICT
    """

    missing_columns = (
        REQUIRED_COLUMNS - set(frame.columns)
    )

    if missing_columns:
        raise ValueError(
            "Colonne obbligatorie mancanti: "
            f"{sorted(missing_columns)}"
        )

    result = frame.copy()

    # Stato iniziale
    result["quality_status"] = "VALID"

    # ---------------------------------------------------------
    # Validazioni strutturali
    # ---------------------------------------------------------

    invalid_date = result[
        "measurement_date"
    ].isna()

    result.loc[
        invalid_date,
        "quality_status",
    ] = "REJECTED"

    invalid_station = result[
        "source_station_id"
    ].isna()

    result.loc[
        invalid_station,
        "quality_status",
    ] = "REJECTED"

    invalid_pollutant = result[
        "pollutant_code"
    ].isna()

    result.loc[
        invalid_pollutant,
        "quality_status",
    ] = "REJECTED"

    invalid_network = result[
        "network"
    ].isna()

    result.loc[
        invalid_network,
        "quality_status",
    ] = "REJECTED"

    # ---------------------------------------------------------
    # Normalizzazione minima
    # ---------------------------------------------------------

    result["source_station_id"] = (
        result["source_station_id"]
        .astype("string")
        .str.strip()
    )

    result["pollutant_code"] = (
        result["pollutant_code"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    result["network"] = (
        result["network"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    # ---------------------------------------------------------
    # Warning sui valori mancanti
    # ---------------------------------------------------------

    if "value" in result.columns:
        missing_value = (
            result["value"].isna()
            & (
                result["quality_status"]
                == "VALID"
            )
        )

        result.loc[
            missing_value,
            "quality_status",
        ] = "VALID_WITH_WARNING"

    # ---------------------------------------------------------
    # Controlli semantici minimi
    # ---------------------------------------------------------

    valid_networks = {
        "RRQA",
        "ADI",
    }

    unexpected_network = (
        result["network"].notna()
        & ~result["network"].isin(
            valid_networks
        )
        & (
            result["quality_status"]
            != "REJECTED"
        )
    )

    result.loc[
        unexpected_network,
        "quality_status",
    ] = "VALID_WITH_WARNING"

    # Valori negativi:
    # non vengono rifiutati automaticamente,
    # ma vengono segnalati.
    if "value" in result.columns:
        negative_values = (
            result["value"].notna()
            & (
                result["value"] < 0
            )
            & (
                result["quality_status"]
                != "REJECTED"
            )
        )

        result.loc[
            negative_values,
            "quality_status",
        ] = "VALID_WITH_WARNING"

    # ---------------------------------------------------------
    # Classificazione duplicati
    # ---------------------------------------------------------

    result = classify_duplicates(
        result
    )

    return result