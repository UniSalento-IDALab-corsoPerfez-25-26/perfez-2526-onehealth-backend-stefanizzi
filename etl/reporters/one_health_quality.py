from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


LOGICAL_KEYS = [
    "indicator_code",
    "year",
    "asl",
    "sex",
    "age_group",
]

MAIN_COLUMNS = [
    "cases",
    "population",
    "prevalence_per_1000",
    "prevalence_percent",
    "pm10_mean_value",
    "pm2_5_mean_value",
    "no2_mean_value",
    "o3_mean_value",
]


def _json_safe(value: Any) -> Any:
    """
    Converte valori pandas/NumPy in oggetti serializzabili JSON.
    """

    if pd.isna(value):
        return None

    if hasattr(value, "item"):
        return value.item()

    return value


def _column_quality(
    frame: pd.DataFrame,
    column: str,
) -> dict[str, Any]:
    """
    Restituisce le informazioni di completezza
    di una singola colonna.
    """

    missing = int(
        frame[column]
        .isna()
        .sum()
    )

    available = int(
        len(frame) - missing
    )

    availability_percent = (
        available / len(frame) * 100
        if len(frame)
        else 0.0
    )

    return {
        "column": column,
        "records": int(len(frame)),
        "available": available,
        "missing": missing,
        "availability_percent": round(
            availability_percent,
            4,
        ),
    }


def build_one_health_quality_report(
    *,
    dataset_path: Path,
    report_dir: Path,
    start_year: int,
    end_year: int,
    dataset_version: str = "1.0.0",
) -> dict[str, Any]:
    """
    Analizza il dataset One Health e genera
    un report JSON e CSV versionato.
    """

    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset One Health non trovato: {dataset_path}"
        )

    frame = pd.read_parquet(
        dataset_path
    )

    if frame.empty:
        raise ValueError(
            "Il dataset One Health è vuoto."
        )

    required_columns = {
        "indicator_code",
        "year",
        "asl",
        "sex",
        "age_group",
        "cases",
        "population",
        "prevalence_per_1000",
    }

    missing_required_columns = (
        required_columns
        - set(frame.columns)
    )

    if missing_required_columns:
        raise ValueError(
            "Colonne richieste mancanti: "
            f"{sorted(missing_required_columns)}"
        )

    generated_at = datetime.now(
        timezone.utc
    )

    timestamp = generated_at.strftime(
        "%Y%m%dT%H%M%SZ"
    )

    # -------------------------------------------------
    # Controlli logici
    # -------------------------------------------------

    duplicate_mask = frame.duplicated(
        subset=LOGICAL_KEYS,
        keep=False,
    )

    duplicate_records = int(
        duplicate_mask.sum()
    )

    duplicate_groups = int(
        frame.loc[
            duplicate_mask,
            LOGICAL_KEYS,
        ]
        .drop_duplicates()
        .shape[0]
    )

    invalid_population = int(
        (
            pd.to_numeric(
                frame["population"],
                errors="coerce",
            )
            <= 0
        ).sum()
    )

    invalid_cases = int(
        (
            pd.to_numeric(
                frame["cases"],
                errors="coerce",
            )
            < 0
        ).sum()
    )

    invalid_prevalence = int(
        (
            pd.to_numeric(
                frame["prevalence_per_1000"],
                errors="coerce",
            )
            < 0
        ).sum()
    )

    # -------------------------------------------------
    # Completezza
    # -------------------------------------------------

    existing_main_columns = [
        column
        for column in MAIN_COLUMNS
        if column in frame.columns
    ]

    column_quality = [
        _column_quality(
            frame,
            column,
        )
        for column in existing_main_columns
    ]

    total_missing = sum(
        item["missing"]
        for item in column_quality
    )

    # -------------------------------------------------
    # Statistiche sanitarie
    # -------------------------------------------------

    prevalence = pd.to_numeric(
        frame["prevalence_per_1000"],
        errors="coerce",
    )

    prevalence_statistics = {
        "count": int(
            prevalence.count()
        ),
        "minimum": _json_safe(
            prevalence.min()
        ),
        "maximum": _json_safe(
            prevalence.max()
        ),
        "mean": _json_safe(
            prevalence.mean()
        ),
        "median": _json_safe(
            prevalence.median()
        ),
        "percentile_95": _json_safe(
            prevalence.quantile(0.95)
        ),
    }

    # -------------------------------------------------
    # Copertura territoriale e temporale
    # -------------------------------------------------

    expected_years = list(
        range(
            start_year,
            end_year + 1,
        )
    )

    actual_years = sorted(
        frame["year"]
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    )

    expected_asl = {
        "BAT",
        "Bari",
        "Brindisi",
        "Foggia",
        "Lecce",
        "Taranto",
    }

    actual_asl = set(
        frame["asl"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    missing_years = sorted(
        set(expected_years)
        - set(actual_years)
    )

    missing_asl = sorted(
        expected_asl
        - actual_asl
    )

    # -------------------------------------------------
    # Esito complessivo
    # -------------------------------------------------

    critical_issues = (
        duplicate_records
        + invalid_population
        + invalid_cases
        + invalid_prevalence
        + len(missing_years)
        + len(missing_asl)
    )

    status = (
        "PASS"
        if critical_issues == 0
        else "FAIL"
    )

    report: dict[str, Any] = {
        "report_type": "one_health_data_quality",
        "dataset": str(dataset_path),
        "dataset_version": dataset_version,
        "generated_at_utc": (
            generated_at.isoformat()
        ),
        "period": {
            "start_year": start_year,
            "end_year": end_year,
            "expected_years": expected_years,
            "actual_years": actual_years,
            "missing_years": missing_years,
        },
        "dimensions": {
            "records": int(len(frame)),
            "columns": int(len(frame.columns)),
            "indicators": sorted(
                frame["indicator_code"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            ),
            "asl": sorted(actual_asl),
            "missing_asl": missing_asl,
            "sexes": sorted(
                frame["sex"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            ),
            "age_groups": sorted(
                frame["age_group"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            ),
        },
        "logical_quality": {
            "duplicate_records":
                duplicate_records,
            "duplicate_groups":
                duplicate_groups,
            "invalid_population":
                invalid_population,
            "invalid_cases":
                invalid_cases,
            "invalid_prevalence":
                invalid_prevalence,
        },
        "completeness": {
            "total_missing_values":
                int(total_missing),
            "columns": column_quality,
        },
        "prevalence_statistics":
            prevalence_statistics,
        "status": status,
        "critical_issue_count":
            int(critical_issues),
    }

    # -------------------------------------------------
    # Scrittura report
    # -------------------------------------------------

    report_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_stem = (
        f"one_health_quality_"
        f"{start_year}_{end_year}_"
        f"{timestamp}"
    )

    json_path = (
        report_dir
        / f"{report_stem}.json"
    )

    csv_path = (
        report_dir
        / f"{report_stem}.csv"
    )

    latest_path = (
        report_dir
        / "latest_quality_report.json"
    )

    json_text = json.dumps(
        report,
        indent=2,
        ensure_ascii=False,
    )

    json_path.write_text(
        json_text,
        encoding="utf-8",
    )

    latest_path.write_text(
        json_text,
        encoding="utf-8",
    )

    pd.DataFrame(
        column_quality
    ).to_csv(
        csv_path,
        index=False,
    )

    print("=" * 70)
    print("DATA QUALITY REPORT")
    print("=" * 70)
    print("Stato:", status)
    print("Record:", len(frame))
    print(
        "Duplicati logici:",
        duplicate_records,
    )
    print(
        "Valori mancanti:",
        total_missing,
    )
    print(
        "Popolazioni non valide:",
        invalid_population,
    )
    print(
        "Conteggi non validi:",
        invalid_cases,
    )
    print(
        "Prevalenze non valide:",
        invalid_prevalence,
    )
    print("Report JSON:", json_path)
    print("Report CSV:", csv_path)
    print("Report latest:", latest_path)

    return report