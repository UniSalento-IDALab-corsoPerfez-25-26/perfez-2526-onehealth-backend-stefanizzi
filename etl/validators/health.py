import pandas as pd


REQUIRED_COLUMNS = {
    "indicator_code",
    "year",
    "geographic_level",
    "geographic_area",
    "sex",
    "age_group",
    "cases",
}


VALID_SEX = {
    "F",
    "M",
    "ALL",
}


VALID_LEVELS = {
    "ASL",
    "REGION",
}


def validate_health_indicators(
    frame: pd.DataFrame,
) -> pd.DataFrame:

    missing = REQUIRED_COLUMNS - set(frame.columns)

    if missing:
        raise ValueError(
            f"Colonne sanitarie mancanti: {sorted(missing)}"
        )

    result = frame.copy()

    result["quality_status"] = "VALID"

    invalid_required = (
        result["year"].isna()
        | result["geographic_area"].isna()
        | result["sex"].isna()
        | result["age_group"].isna()
        | result["cases"].isna()
    )

    result.loc[
        invalid_required,
        "quality_status",
    ] = "REJECTED"

    invalid_cases = (
        result["cases"].notna()
        & (result["cases"] < 0)
    )

    result.loc[
        invalid_cases,
        "quality_status",
    ] = "REJECTED"

    invalid_sex = (
        ~result["sex"].isin(VALID_SEX)
        & result["sex"].notna()
    )

    result.loc[
        invalid_sex
        & (result["quality_status"] == "VALID"),
        "quality_status",
    ] = "VALID_WITH_WARNING"

    invalid_level = (
        ~result["geographic_level"].isin(
            VALID_LEVELS
        )
    )

    result.loc[
        invalid_level
        & (result["quality_status"] == "VALID"),
        "quality_status",
    ] = "VALID_WITH_WARNING"

    duplicate_mask = result.duplicated(
        subset=[
            "indicator_code",
            "year",
            "geographic_level",
            "geographic_area",
            "sex",
            "age_group",
        ],
        keep=False,
    )

    result.loc[
        duplicate_mask,
        "quality_status",
    ] = "DUPLICATE"

    return result