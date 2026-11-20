from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


ONE_HEALTH_DATASET_PATH = Path(
    "data/processed/one_health/"
    "one_health_dataset_2021_2023.parquet"
)

ENVIRONMENTAL_EXPOSURE_PATH = Path(
    "data/processed/one_health/"
    "environmental_exposure_asl_2021_2023.parquet"
)

HEALTH_PREVALENCE_PATH = Path(
    "data/processed/health/"
    "health_prevalence_2020_2023.parquet"
)

BPCO_PREVALENCE_PATH = Path(
    "data/processed/health/"
    "bpco_prevalence_2020_2023.parquet"
)

QUALITY_REPORT_PATH = Path(
    "data/reports/one_health/"
    "latest_quality_report.json"
)

DATASET_MANIFEST_PATH = Path(
    "data/manifests/one_health/"
    "latest_manifest.json"
)

class DatasetNotAvailableError(RuntimeError):
    """Il dataset richiesto non è stato ancora generato."""


def _read_parquet(path: Path) -> pd.DataFrame:
    # Governance OneHealthAI:
    # il Master DSS non può leggere artefatti di ricerca
    # registrati senza approvazione esplicita.
    from scripts.one_health.artifact_access import (
        load_registry,
        resolve_artifact,
        AccessDenied,
        PROJECT_ROOT,
    )

    registry = load_registry()
    requested = path.resolve()

    matches = [
        artifact
        for artifact in registry["artifacts"]
        if (
            PROJECT_ROOT / artifact["path"]
        ).resolve() == requested
    ]

    if len(matches) != 1:
        raise PermissionError(
            "Dataset non registrato o registrazione ambigua"
        )

    artifact = matches[0]

    try:
        authorized = resolve_artifact(
            artifact["id"],
            "master"
        )
    except AccessDenied as exc:
        raise PermissionError(
            f"Accesso Master DSS negato: {artifact['id']}"
        ) from exc

    if not authorized.exists():
        raise DatasetNotAvailableError(
            f"Dataset non disponibile: {authorized}. "
            "Eseguire prima la relativa pipeline ETL."
        )

    return pd.read_parquet(authorized)


def _normalize_optional_text(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    normalized = value.strip()

    return normalized or None


def _records(
    frame: pd.DataFrame,
) -> list[dict[str, Any]]:
    """
    Converte un DataFrame in record JSON-safe.

    NaN, NaT e valori pandas mancanti diventano None.
    """

    result = frame.copy()

    result = result.astype(object).where(
        pd.notna(result),
        None,
    )

    return result.to_dict(
        orient="records"
    )


def get_one_health_data(
    *,
    start_year: int | None = None,
    end_year: int | None = None,
    asl: str | None = None,
    indicator: str | None = None,
    sex: str | None = None,
    age_group: str | None = None,
    limit: int = 1000,
    offset: int = 0,
) -> dict[str, Any]:

    frame = _read_parquet(
        ONE_HEALTH_DATASET_PATH
    )

    asl = _normalize_optional_text(asl)
    indicator = _normalize_optional_text(indicator)
    sex = _normalize_optional_text(sex)
    age_group = _normalize_optional_text(age_group)

    if start_year is not None:
        frame = frame[
            frame["year"] >= start_year
        ]

    if end_year is not None:
        frame = frame[
            frame["year"] <= end_year
        ]

    if asl is not None:
        frame = frame[
            frame["asl"].astype(str).str.casefold()
            == asl.casefold()
        ]

    if indicator is not None:
        frame = frame[
            frame["indicator_code"]
            .astype(str)
            .str.casefold()
            == indicator.casefold()
        ]

    if sex is not None:
        frame = frame[
            frame["sex"].astype(str).str.casefold()
            == sex.casefold()
        ]

    if age_group is not None:
        frame = frame[
            frame["age_group"]
            .astype(str)
            .str.casefold()
            == age_group.casefold()
        ]

    frame = frame.sort_values(
        [
            "indicator_code",
            "year",
            "asl",
            "sex",
            "age_group",
        ]
    )

    total = len(frame)

    page = frame.iloc[
        offset: offset + limit
    ]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "count": len(page),
        "data": _records(page),
    }


def get_one_health_summary() -> dict[str, Any]:
    frame = _read_parquet(
        ONE_HEALTH_DATASET_PATH
    )

    environmental_columns = [
        column
        for column in frame.columns
        if column.startswith(
            (
                "pm10_",
                "pm2_5_",
                "no2_",
                "o3_",
            )
        )
    ]

    return {
        "records": len(frame),
        "columns": len(frame.columns),
        "years": sorted(
            frame["year"]
            .dropna()
            .astype(int)
            .unique()
            .tolist()
        ),
        "asl": sorted(
            frame["asl"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        ),
        "indicators": sorted(
            frame["indicator_code"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        ),
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
        "environmental_variables":
            environmental_columns,
        "dataset_versions": sorted(
            frame.get(
                "dataset_version",
                pd.Series(dtype="string"),
            )
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        ),
    }


def get_prevalence_data(
    *,
    start_year: int | None = None,
    end_year: int | None = None,
    asl: str | None = None,
    indicator: str | None = None,
    sex: str | None = None,
    age_group: str | None = None,
    limit: int = 1000,
    offset: int = 0,
) -> dict[str, Any]:

    path = (
        HEALTH_PREVALENCE_PATH
        if HEALTH_PREVALENCE_PATH.exists()
        else BPCO_PREVALENCE_PATH
    )

    frame = _read_parquet(path)

    asl = _normalize_optional_text(asl)
    indicator = _normalize_optional_text(indicator)
    sex = _normalize_optional_text(sex)
    age_group = _normalize_optional_text(age_group)

    if start_year is not None:
        frame = frame[
            frame["year"] >= start_year
        ]

    if end_year is not None:
        frame = frame[
            frame["year"] <= end_year
        ]

    if asl is not None:
        frame = frame[
            frame["asl"].astype(str).str.casefold()
            == asl.casefold()
        ]

    if indicator is not None:
        frame = frame[
            frame["indicator_code"]
            .astype(str)
            .str.casefold()
            == indicator.casefold()
        ]

    if sex is not None:
        frame = frame[
            frame["sex"].astype(str).str.casefold()
            == sex.casefold()
        ]

    if age_group is not None:
        frame = frame[
            frame["age_group"]
            .astype(str)
            .str.casefold()
            == age_group.casefold()
        ]

    frame = frame.sort_values(
        [
            "indicator_code",
            "year",
            "asl",
            "sex",
            "age_group",
        ]
    )

    total = len(frame)

    page = frame.iloc[
        offset: offset + limit
    ]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "count": len(page),
        "data": _records(page),
    }


def get_environmental_exposure(
    *,
    start_year: int | None = None,
    end_year: int | None = None,
    asl: str | None = None,
    pollutant: str | None = None,
    limit: int = 1000,
    offset: int = 0,
) -> dict[str, Any]:

    frame = _read_parquet(
        ENVIRONMENTAL_EXPOSURE_PATH
    )

    asl = _normalize_optional_text(asl)
    pollutant = _normalize_optional_text(pollutant)

    if start_year is not None:
        frame = frame[
            frame["year"] >= start_year
        ]

    if end_year is not None:
        frame = frame[
            frame["year"] <= end_year
        ]

    if asl is not None:
        frame = frame[
            frame["asl"].astype(str).str.casefold()
            == asl.casefold()
        ]

    if pollutant is not None:
        frame = frame[
            frame["pollutant_code"]
            .astype(str)
            .str.casefold()
            == pollutant.casefold()
        ]

    frame = frame.sort_values(
        [
            "year",
            "asl",
            "pollutant_code",
        ]
    )

    total = len(frame)

    page = frame.iloc[
        offset: offset + limit
    ]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "count": len(page),
        "data": _records(page),
    }

def get_quality_report() -> dict[str, Any]:
    if not QUALITY_REPORT_PATH.exists():
        raise DatasetNotAvailableError(
            "Data Quality Report non disponibile. "
            "Eseguire prima arpa build-one-health."
        )

    import json

    return json.loads(
        QUALITY_REPORT_PATH.read_text(
            encoding="utf-8"
        )
    )

def get_dataset_manifest() -> dict[str, Any]:
    if not DATASET_MANIFEST_PATH.exists():
        raise DatasetNotAvailableError(
            "Manifest del dataset non disponibile. "
            "Eseguire prima arpa build-one-health."
        )

    import json

    return json.loads(
        DATASET_MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )