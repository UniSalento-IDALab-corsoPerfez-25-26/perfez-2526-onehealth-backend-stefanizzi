import pandas as pd


REQUIRED_COLUMNS = {
    "source_pollutant_id",
    "code",
}


def validate_pollutants(
    frame: pd.DataFrame,
) -> pd.DataFrame:

    missing = REQUIRED_COLUMNS - set(frame.columns)

    if missing:
        raise ValueError(
            f"Colonne inquinanti mancanti: {sorted(missing)}"
        )

    result = frame.copy()

    result["quality_status"] = "VALID"

    required_mask = (
        result["source_pollutant_id"].isna()
        | result["code"].isna()
    )

    result.loc[
        required_mask,
        "quality_status",
    ] = "REJECTED"

    duplicate_id = result.duplicated(
        subset=["source_pollutant_id"],
        keep=False,
    )

    duplicate_code = result.duplicated(
        subset=["code"],
        keep=False,
    )

    result.loc[
        duplicate_id | duplicate_code,
        "quality_status",
    ] = "DUPLICATE"

    return result