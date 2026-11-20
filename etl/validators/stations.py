import pandas as pd


REQUIRED_COLUMNS = {
    "source_station_id",
    "name",
    "municipality",
    "province",
    "network",
}


VALID_NETWORKS = {
    "RRQA",
    "ADI",
}


def validate_stations(frame: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - set(frame.columns)

    if missing:
        raise ValueError(
            f"Colonne stazioni mancanti: {sorted(missing)}"
        )

    result = frame.copy()

    result["quality_status"] = "VALID"

    required_mask = (
        result["source_station_id"].isna()
        | result["name"].isna()
        | result["province"].isna()
    )

    result.loc[
        required_mask,
        "quality_status",
    ] = "REJECTED"

    if "network" in result.columns:
        invalid_network = (
            ~result["network"].isin(VALID_NETWORKS)
            & result["network"].notna()
        )

        result.loc[
            invalid_network
            & (result["quality_status"] == "VALID"),
            "quality_status",
        ] = "VALID_WITH_WARNING"

    if {
        "longitude",
        "latitude",
    }.issubset(result.columns):

        invalid_coordinates = (
            result["longitude"].isna()
            | result["latitude"].isna()
            | ~result["longitude"].between(14, 19)
            | ~result["latitude"].between(39, 43)
        )

        result.loc[
            invalid_coordinates
            & (result["quality_status"] == "VALID"),
            "quality_status",
        ] = "VALID_WITH_WARNING"

    duplicate_mask = result.duplicated(
        subset=["source_station_id"],
        keep=False,
    )

    result.loc[
        duplicate_mask,
        "quality_status",
    ] = "DUPLICATE"

    return result