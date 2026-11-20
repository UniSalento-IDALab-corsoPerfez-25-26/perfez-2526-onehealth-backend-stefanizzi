from __future__ import annotations

import pandas as pd


LOGICAL_KEY = [
    "source_station_id",
    "measurement_datetime",
]


def validate_meteorological_measurements(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    """
    Applica controlli strutturali e fisici di base.

    I limiti sono volutamente ampi: servono a individuare
    errori evidenti, non a validare scientificamente
    la misura ARPA.
    """

    required_columns = {
        "measurement_datetime",
        "source_station_id",
        "station_name",
        "latitude",
        "longitude",
    }

    missing = (
        required_columns
        - set(frame.columns)
    )

    if missing:
        raise ValueError(
            "Colonne meteorologiche mancanti: "
            f"{sorted(missing)}"
        )

    result = frame.copy()

    result["quality_status"] = "VALID"
    result["quality_notes"] = pd.Series(
        "",
        index=result.index,
        dtype="string",
    )

    def add_issue(
        mask: pd.Series,
        status: str,
        message: str,
    ) -> None:
        if not mask.any():
            return

        current = result.loc[
            mask,
            "quality_notes",
        ].fillna("")

        result.loc[
            mask,
            "quality_notes",
        ] = current.where(
            current == "",
            current + "; ",
        ) + message

        if status == "REJECTED":
            result.loc[
                mask,
                "quality_status",
            ] = "REJECTED"

        elif status == "VALID_WITH_WARNING":
            result.loc[
                mask
                & (
                    result["quality_status"]
                    == "VALID"
                ),
                "quality_status",
            ] = "VALID_WITH_WARNING"

    add_issue(
        result["measurement_datetime"].isna(),
        "REJECTED",
        "timestamp mancante o non valido",
    )

    add_issue(
        result["source_station_id"].isna(),
        "REJECTED",
        "identificativo stazione mancante",
    )

    add_issue(
        result["latitude"].isna()
        | result["longitude"].isna(),
        "REJECTED",
        "coordinate mancanti",
    )

    add_issue(
        ~result["latitude"].between(
            -90,
            90,
            inclusive="both",
        ),
        "REJECTED",
        "latitudine fuori intervallo",
    )

    add_issue(
        ~result["longitude"].between(
            -180,
            180,
            inclusive="both",
        ),
        "REJECTED",
        "longitudine fuori intervallo",
    )

    if "temperature" in result.columns:
        add_issue(
            result["temperature"].notna()
            & ~result["temperature"].between(
                -40,
                60,
                inclusive="both",
            ),
            "VALID_WITH_WARNING",
            "temperatura fuori intervallo plausibile",
        )

    if "relative_humidity" in result.columns:
        add_issue(
            result["relative_humidity"].notna()
            & ~result["relative_humidity"].between(
                0,
                100,
                inclusive="both",
            ),
            "VALID_WITH_WARNING",
            "umidità relativa fuori intervallo",
        )

    if "precipitation" in result.columns:
        add_issue(
            result["precipitation"].notna()
            & (
                result["precipitation"] < 0
            ),
            "VALID_WITH_WARNING",
            "precipitazione negativa",
        )

    if "wind_speed" in result.columns:
        add_issue(
            result["wind_speed"].notna()
            & (
                result["wind_speed"] < 0
            ),
            "VALID_WITH_WARNING",
            "velocità del vento negativa",
        )

    if "wind_direction" in result.columns:
        add_issue(
            result["wind_direction"].notna()
            & ~result["wind_direction"].between(
                0,
                360,
                inclusive="both",
            ),
            "VALID_WITH_WARNING",
            "direzione del vento fuori intervallo",
        )

    if "solar_radiation" in result.columns:
        add_issue(
            result["solar_radiation"].notna()
            & (
                result["solar_radiation"] < 0
            ),
            "VALID_WITH_WARNING",
            "radiazione solare negativa",
        )

    if "atmospheric_pressure" in result.columns:
        add_issue(
            result["atmospheric_pressure"].notna()
            & ~result[
                "atmospheric_pressure"
            ].between(
                850,
                1100,
                inclusive="both",
            ),
            "VALID_WITH_WARNING",
            "pressione atmosferica fuori intervallo",
        )

    duplicate_mask = result.duplicated(
        subset=LOGICAL_KEY,
        keep=False,
    )

    result.loc[
        duplicate_mask
        & (
            result["quality_status"]
            != "REJECTED"
        ),
        "quality_status",
    ] = "DUPLICATE"

    result.loc[
        duplicate_mask,
        "quality_notes",
    ] = (
        result.loc[
            duplicate_mask,
            "quality_notes",
        ]
        .fillna("")
        .where(
            result.loc[
                duplicate_mask,
                "quality_notes",
            ].fillna("") == "",
            result.loc[
                duplicate_mask,
                "quality_notes",
            ].fillna("") + "; ",
        )
        + "chiave stazione-timestamp duplicata"
    )

    return result