from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import select

from app.core.database import SessionLocal
from etl.release_guard import assert_legacy_output_writable
from app.models import (
    EnvironmentalMeasurement,
    MonitoringStation,
    Pollutant,
)


PROVINCE_TO_ASL = {
    "BARI": "Bari",
    "BAT": "BAT",
    "BARLETTA-ANDRIA-TRANI": "BAT",
    "BRINDISI": "Brindisi",
    "FOGGIA": "Foggia",
    "LECCE": "Lecce",
    "TARANTO": "Taranto",
}


CORE_POLLUTANTS = {
    "PM10",
    "PM2.5",
    "NO2",
    "O3",
}


def _normalize_asl(value: object) -> str | None:
    if pd.isna(value):
        return None

    normalized = str(value).strip().upper()

    return PROVINCE_TO_ASL.get(normalized)


def _safe_slug(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace(".", "_")
        .replace(" ", "_")
        .replace("-", "_")
    )


def extract_environmental_measurements(
    *,
    start_year: int,
    end_year: int,
    pollutants: set[str] | None = None,
) -> pd.DataFrame:
    """
    Estrae dal database le misure ambientali necessarie
    alla costruzione degli indicatori annuali per ASL.
    """

    if start_year > end_year:
        raise ValueError(
            "start_year non può essere maggiore di end_year."
        )

    selected_pollutants = pollutants or CORE_POLLUTANTS

    with SessionLocal() as session:
        query = (
            select(
                EnvironmentalMeasurement.measurement_date,
                EnvironmentalMeasurement.value,
                EnvironmentalMeasurement.source_limit,
                EnvironmentalMeasurement.quality_status,
                EnvironmentalMeasurement.station_id,
                MonitoringStation.province,
                Pollutant.code.label("pollutant_code"),
            )
            .join(
                MonitoringStation,
                MonitoringStation.id
                == EnvironmentalMeasurement.station_id,
            )
            .join(
                Pollutant,
                Pollutant.id
                == EnvironmentalMeasurement.pollutant_id,
            )
            .where(
                EnvironmentalMeasurement.measurement_date
                >= pd.Timestamp(
                    year=start_year,
                    month=1,
                    day=1,
                ).date(),
                EnvironmentalMeasurement.measurement_date
                <= pd.Timestamp(
                    year=end_year,
                    month=12,
                    day=31,
                ).date(),
                Pollutant.code.in_(
                    sorted(selected_pollutants)
                ),
            )
        )

        rows = session.execute(query).all()

    frame = pd.DataFrame(
        rows,
        columns=[
            "measurement_date",
            "value",
            "source_limit",
            "quality_status",
            "station_id",
            "province",
            "pollutant_code",
        ],
    )

    if frame.empty:
        raise ValueError(
            "Nessuna misura ambientale trovata "
            f"tra {start_year} e {end_year}."
        )

    frame["measurement_date"] = pd.to_datetime(
        frame["measurement_date"],
        errors="coerce",
    )

    frame["year"] = (
        frame["measurement_date"]
        .dt.year
        .astype("Int64")
    )

    frame["pollutant_code"] = (
        frame["pollutant_code"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    frame["value"] = pd.to_numeric(
        frame["value"],
        errors="coerce",
    )

    frame["source_limit"] = pd.to_numeric(
        frame["source_limit"],
        errors="coerce",
    )

    frame["asl"] = frame["province"].apply(
        _normalize_asl
    )

    unresolved = frame[
        frame["asl"].isna()
    ]

    if not unresolved.empty:
        provinces = sorted(
            unresolved["province"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        raise ValueError(
            "Province ambientali senza mapping ASL: "
            f"{provinces}"
        )

    return frame


def build_environmental_exposure(
    *,
    start_year: int,
    end_year: int,
    output_long_path: Path,
    output_wide_path: Path,
    pollutants: set[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Costruisce gli indicatori annuali di esposizione
    ambientale per ASL e inquinante.

    Gli indicatori sono aggregazioni descrittive delle
    osservazioni stazione-giorno disponibili.
    """

    assert_legacy_output_writable(output_long_path)
    assert_legacy_output_writable(output_wide_path)
    frame = extract_environmental_measurements(
        start_year=start_year,
        end_year=end_year,
        pollutants=pollutants,
    )

    frame["has_value"] = (
        frame["value"].notna()
    )

    frame["is_exceedance"] = (
        frame["value"].notna()
        & frame["source_limit"].notna()
        & (
            frame["value"]
            > frame["source_limit"]
        )
    )

    group_columns = [
        "year",
        "asl",
        "pollutant_code",
    ]

    exposure = (
        frame.groupby(
            group_columns,
            as_index=False,
            dropna=False,
        )
        .agg(
            records=(
                "value",
                "size",
            ),
            valid_values=(
                "has_value",
                "sum",
            ),
            stations=(
                "station_id",
                "nunique",
            ),
            days=(
                "measurement_date",
                "nunique",
            ),
            mean_value=(
                "value",
                "mean",
            ),
            median_value=(
                "value",
                "median",
            ),
            maximum_value=(
                "value",
                "max",
            ),
            exceedance_records=(
                "is_exceedance",
                "sum",
            ),
        )
    )

    percentile_95 = (
        frame[
            frame["value"].notna()
        ]
        .groupby(
            group_columns,
            dropna=False,
        )["value"]
        .quantile(0.95)
        .rename("percentile_95")
        .reset_index()
    )

    exposure = exposure.merge(
        percentile_95,
        on=group_columns,
        how="left",
        validate="one_to_one",
    )

    exposure["availability_percent"] = (
        exposure["valid_values"]
        / exposure["records"]
        * 100
    )

    exposure["exceedance_percent"] = np.where(
        exposure["valid_values"] > 0,
        (
            exposure["exceedance_records"]
            / exposure["valid_values"]
            * 100
        ),
        np.nan,
    )

    numeric_columns = [
        "mean_value",
        "median_value",
        "maximum_value",
        "percentile_95",
        "availability_percent",
        "exceedance_percent",
    ]

    exposure[numeric_columns] = (
        exposure[numeric_columns]
        .round(4)
    )

    exposure["source"] = "ARPAP"
    exposure["quality_status"] = "VALID"

    exposure = exposure.sort_values(
        [
            "year",
            "asl",
            "pollutant_code",
        ]
    ).reset_index(drop=True)

    output_long_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    exposure.to_parquet(
        output_long_path,
        index=False,
    )

    # --------------------------------------------------
    # Formato wide: una riga per anno e ASL
    # --------------------------------------------------

    metrics = [
        "mean_value",
        "median_value",
        "maximum_value",
        "percentile_95",
        "availability_percent",
        "exceedance_records",
        "exceedance_percent",
        "stations",
        "days",
    ]

    wide_parts: list[pd.DataFrame] = []

    for metric in metrics:
        pivot = exposure.pivot(
            index=[
                "year",
                "asl",
            ],
            columns="pollutant_code",
            values=metric,
        )

        pivot.columns = [
            f"{_safe_slug(pollutant)}_{metric}"
            for pollutant in pivot.columns
        ]

        wide_parts.append(pivot)

    exposure_wide = pd.concat(
        wide_parts,
        axis=1,
    ).reset_index()

    exposure_wide = exposure_wide.sort_values(
        [
            "year",
            "asl",
        ]
    ).reset_index(drop=True)

    output_wide_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    exposure_wide.to_parquet(
        output_wide_path,
        index=False,
    )

    print("=" * 70)
    print("INDICATORI AMBIENTALI ANNUALI")
    print("=" * 70)
    print("Record long:", len(exposure))
    print("Record wide:", len(exposure_wide))
    print(
        "Anni:",
        sorted(
            exposure["year"]
            .astype(int)
            .unique()
            .tolist()
        ),
    )
    print(
        "ASL:",
        sorted(
            exposure["asl"]
            .unique()
            .tolist()
        ),
    )
    print(
        "Inquinanti:",
        sorted(
            exposure["pollutant_code"]
            .unique()
            .tolist()
        ),
    )
    print("File long:", output_long_path)
    print("File wide:", output_wide_path)

    return exposure, exposure_wide


def build_one_health_dataset(
    *,
    health_prevalence_path: Path,
    environmental_exposure_path: Path,
    output_path: Path,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    """
    Integra prevalenze sanitarie ed esposizioni
    ambientali annuali mediante anno e ASL.
    """

    assert_legacy_output_writable(output_path)
    if not health_prevalence_path.exists():
        raise FileNotFoundError(
            "File delle prevalenze sanitarie non trovato: "
            f"{health_prevalence_path}"
        )

    if not environmental_exposure_path.exists():
        raise FileNotFoundError(
            "File delle esposizioni ambientali non trovato: "
            f"{environmental_exposure_path}"
        )

    health = pd.read_parquet(
        health_prevalence_path
    )

    environment = pd.read_parquet(
        environmental_exposure_path
    )

    required_health_columns = {
        "indicator_code",
        "year",
        "asl",
        "sex",
        "age_group",
        "cases",
        "population",
        "prevalence_per_1000",
        "prevalence_percent",
    }

    missing_health = (
        required_health_columns
        - set(health.columns)
    )

    if missing_health:
        raise ValueError(
            "Colonne sanitarie mancanti: "
            f"{sorted(missing_health)}"
        )

    required_environment_columns = {
        "year",
        "asl",
    }

    missing_environment = (
        required_environment_columns
        - set(environment.columns)
    )

    if missing_environment:
        raise ValueError(
            "Colonne ambientali mancanti: "
            f"{sorted(missing_environment)}"
        )

    health = health[
        health["year"].between(
            start_year,
            end_year,
        )
    ].copy()

    environment = environment[
        environment["year"].between(
            start_year,
            end_year,
        )
    ].copy()

    environment_duplicates = (
        environment.duplicated(
            subset=[
                "year",
                "asl",
            ],
            keep=False,
        )
    )

    if environment_duplicates.any():
        raise ValueError(
            "Il dataset ambientale wide contiene "
            "chiavi anno-ASL duplicate."
        )

    result = health.merge(
        environment,
        on=[
            "year",
            "asl",
        ],
        how="left",
        validate="many_to_one",
        indicator=True,
    )

    unresolved = result[
        result["_merge"] != "both"
    ]

    if not unresolved.empty:
        keys = (
            unresolved[
                [
                    "year",
                    "asl",
                ]
            ]
            .drop_duplicates()
            .sort_values(
                [
                    "year",
                    "asl",
                ]
            )
        )

        raise ValueError(
            f"{len(unresolved)} record sanitari "
            "senza indicatori ambientali.\n"
            f"{keys.to_string(index=False)}"
        )

    result = result.drop(
        columns="_merge"
    )

    result["dataset_version"] = "1.0"
    result["integration_level"] = "ASL_YEAR"
    result["quality_status_integrated"] = "VALID"

    result = result.sort_values(
        [
            "indicator_code",
            "year",
            "asl",
            "sex",
            "age_group",
        ]
    ).reset_index(drop=True)

    duplicate_keys = [
        "indicator_code",
        "year",
        "asl",
        "sex",
        "age_group",
    ]

    duplicate_mask = result.duplicated(
        subset=duplicate_keys,
        keep=False,
    )

    if duplicate_mask.any():
        raise ValueError(
            "Il dataset One Health contiene "
            "chiavi logiche duplicate."
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_parquet(
        output_path,
        index=False,
    )

    print("=" * 70)
    print("DATASET ONE HEALTH CREATO")
    print("=" * 70)
    print("Record:", len(result))
    print(
        "Anni:",
        sorted(
            result["year"]
            .astype(int)
            .unique()
            .tolist()
        ),
    )
    print(
        "Indicatori:",
        sorted(
            result["indicator_code"]
            .unique()
            .tolist()
        ),
    )
    print(
        "ASL:",
        sorted(
            result["asl"]
            .unique()
            .tolist()
        ),
    )
    print("Join non risolti: 0")
    print("Duplicati logici: 0")
    print("File:", output_path)

    return result
    